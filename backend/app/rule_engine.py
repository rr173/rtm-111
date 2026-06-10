import asyncio
import time
import socket
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import httpx
import re
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import (
    ProbeTarget,
    ProbeRule,
    ProbeRuleVersion,
    ProbeRuleStep,
    ProbeRuleExecution,
    ProbeRuleStepExecution,
    ProbeResult,
)


STEP_TYPE_HTTP_STATUS = "http_status"
STEP_TYPE_HTTP_BODY = "http_body_match"
STEP_TYPE_TCP = "tcp_connect"
STEP_TYPE_DNS = "dns_resolve"
STEP_TYPE_LATENCY = "latency_threshold"

VALID_STEP_TYPES = {
    STEP_TYPE_HTTP_STATUS: "HTTP状态码检查",
    STEP_TYPE_HTTP_BODY: "HTTP响应体匹配",
    STEP_TYPE_TCP: "TCP连通性",
    STEP_TYPE_DNS: "DNS解析",
    STEP_TYPE_LATENCY: "延迟阈值",
}

MODE_SEQUENCE = "sequence"
MODE_PARALLEL = "parallel"


class RuleEngine:
    def __init__(self):
        pass

    def get_current_rule_version(self, db: Session, rule_id: int) -> Optional[ProbeRuleVersion]:
        rule = db.query(ProbeRule).filter(ProbeRule.id == rule_id).first()
        if not rule:
            return None

        if rule.current_version_id:
            version = db.query(ProbeRuleVersion).filter(
                ProbeRuleVersion.id == rule.current_version_id
            ).first()
            if version:
                return version

        version = db.query(ProbeRuleVersion).filter(
            ProbeRuleVersion.rule_id == rule_id
        ).order_by(ProbeRuleVersion.version.desc()).first()
        return version

    async def execute_rule(self, target: ProbeTarget) -> dict:
        start_time = time.time()
        db = SessionLocal()
        try:
            version = self.get_current_rule_version(db, target.rule_id)
            if not version:
                return {
                    "success": False,
                    "latency_ms": (time.time() - start_time) * 1000,
                    "error_message": "No valid rule version found",
                    "timestamp": datetime.utcnow(),
                    "step_results": [],
                    "version_id": None,
                    "failed_step_id": None,
                }

            steps = db.query(ProbeRuleStep).filter(
                ProbeRuleStep.version_id == version.id
            ).order_by(ProbeRuleStep.step_order.asc()).all()

            if not steps:
                return {
                    "success": False,
                    "latency_ms": (time.time() - start_time) * 1000,
                    "error_message": "Rule has no steps",
                    "timestamp": datetime.utcnow(),
                    "step_results": [],
                    "version_id": version.id,
                    "failed_step_id": None,
                }

            rule_execution = ProbeRuleExecution(
                target_id=target.id,
                version_id=version.id,
                timestamp=datetime.utcnow(),
                success=False,
                latency_ms=None,
                error_message=None,
                failed_step_id=None,
            )
            db.add(rule_execution)
            db.flush()

            step_results = []
            overall_success = False
            failed_step_id = None
            error_message = None

            if version.execution_mode == MODE_SEQUENCE:
                step_results, overall_success, failed_step_id, error_message = await self._execute_sequence(
                    db, steps, rule_execution.id
                )
            elif version.execution_mode == MODE_PARALLEL:
                step_results, overall_success, failed_step_id, error_message = await self._execute_parallel(
                    db, steps, rule_execution.id
                )
            else:
                error_message = f"Unknown execution mode: {version.execution_mode}"
                step_results = []

            total_latency = (time.time() - start_time) * 1000

            rule_execution.success = overall_success
            rule_execution.latency_ms = total_latency
            rule_execution.error_message = error_message
            rule_execution.failed_step_id = failed_step_id

            db.commit()

            return {
                "success": overall_success,
                "latency_ms": total_latency,
                "error_message": error_message,
                "timestamp": rule_execution.timestamp,
                "step_results": step_results,
                "version_id": version.id,
                "failed_step_id": failed_step_id,
                "rule_execution_id": rule_execution.id,
            }
        except Exception as e:
            db.rollback()
            return {
                "success": False,
                "latency_ms": (time.time() - start_time) * 1000,
                "error_message": f"Rule execution error: {str(e)}",
                "timestamp": datetime.utcnow(),
                "step_results": [],
                "version_id": None,
                "failed_step_id": None,
            }
        finally:
            db.close()

    async def _execute_sequence(
        self, db: Session, steps: List[ProbeRuleStep], rule_execution_id: int
    ) -> Tuple[List[dict], bool, Optional[int], Optional[str]]:
        step_results = []
        overall_success = True
        failed_step_id = None
        error_message = None

        for step in steps:
            result = await self._execute_step(step)
            step_results.append(result)

            step_exec = ProbeRuleStepExecution(
                rule_execution_id=rule_execution_id,
                step_id=step.id,
                timestamp=result["timestamp"],
                success=result["success"],
                latency_ms=result["latency_ms"],
                error_message=result["error_message"],
                raw_response=result.get("raw_response"),
            )
            db.add(step_exec)

            if not result["success"]:
                overall_success = False
                failed_step_id = step.id
                error_message = f"Step '{step.name}' failed: {result['error_message'] or 'Unknown error'}"
                break

        return step_results, overall_success, failed_step_id, error_message

    async def _execute_parallel(
        self, db: Session, steps: List[ProbeRuleStep], rule_execution_id: int
    ) -> Tuple[List[dict], bool, Optional[int], Optional[str]]:
        tasks = [self._execute_step(step) for step in steps]
        results = await asyncio.gather(*tasks)
        step_results = list(results)

        for step, result in zip(steps, step_results):
            step_exec = ProbeRuleStepExecution(
                rule_execution_id=rule_execution_id,
                step_id=step.id,
                timestamp=result["timestamp"],
                success=result["success"],
                latency_ms=result["latency_ms"],
                error_message=result["error_message"],
                raw_response=result.get("raw_response"),
            )
            db.add(step_exec)

        overall_success = any(r["success"] for r in step_results)

        if not overall_success:
            failed_step = None
            for step, result in zip(steps, step_results):
                if not result["success"]:
                    failed_step = step
                    break
            if failed_step:
                failed_step_id = failed_step.id
                failed_result = next(r for r in step_results if not r["success"])
                error_message = f"All parallel steps failed. First failure at step '{failed_step.name}': {failed_result['error_message'] or 'Unknown error'}"
            else:
                failed_step_id = None
                error_message = "All parallel steps failed"
        else:
            failed_step_id = None
            error_message = None

        return step_results, overall_success, failed_step_id, error_message

    async def _execute_step(self, step: ProbeRuleStep) -> dict:
        step_type = step.step_type
        config = step.config or {}
        timeout = step.timeout
        pass_condition = step.pass_condition or {}

        handler = getattr(self, f"_step_{step_type}", None)
        if not handler:
            return {
                "step_id": step.id,
                "success": False,
                "latency_ms": 0,
                "error_message": f"Unknown step type: {step_type}",
                "raw_response": None,
                "timestamp": datetime.utcnow(),
            }

        try:
            result = await handler(config, timeout, pass_condition)
            result["step_id"] = step.id
            if "timestamp" not in result:
                result["timestamp"] = datetime.utcnow()
            return result
        except Exception as e:
            return {
                "step_id": step.id,
                "success": False,
                "latency_ms": None,
                "error_message": f"Step execution exception: {str(e)}",
                "raw_response": None,
                "timestamp": datetime.utcnow(),
            }

    async def _step_http_status(self, config: dict, timeout: int, pass_condition: dict) -> dict:
        url = config.get("url", "")
        method = config.get("method", "GET").upper()
        follow_redirects = config.get("follow_redirects", False)
        expected_codes = pass_condition.get("expected_codes", ["200"])

        if not url:
            return {
                "success": False,
                "latency_ms": 0,
                "error_message": "URL not configured",
                "raw_response": None,
            }

        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=follow_redirects) as client:
                if method == "GET":
                    response = await client.get(url)
                elif method == "POST":
                    response = await client.post(url, json=config.get("body"))
                elif method == "HEAD":
                    response = await client.head(url)
                else:
                    response = await client.request(method, url)

                latency = (time.time() - start) * 1000
                actual_code = str(response.status_code)

                in_expected = False
                for expected in expected_codes:
                    expected = str(expected).strip()
                    if "-" in expected:
                        parts = expected.split("-")
                        if len(parts) == 2:
                            try:
                                low, high = int(parts[0]), int(parts[1])
                                if low <= int(actual_code) <= high:
                                    in_expected = True
                                    break
                            except ValueError:
                                pass
                    elif actual_code == expected:
                        in_expected = True
                        break

                if in_expected:
                    return {
                        "success": True,
                        "latency_ms": latency,
                        "error_message": None,
                        "raw_response": f"HTTP {actual_code}",
                    }
                else:
                    return {
                        "success": False,
                        "latency_ms": latency,
                        "error_message": f"Status code mismatch: expected {expected_codes}, got {actual_code}",
                        "raw_response": f"HTTP {actual_code}",
                    }
        except httpx.TimeoutException:
            return {
                "success": False,
                "latency_ms": timeout * 1000,
                "error_message": "HTTP connection timeout",
                "raw_response": None,
            }
        except Exception as e:
            return {
                "success": False,
                "latency_ms": (time.time() - start) * 1000,
                "error_message": str(e),
                "raw_response": None,
            }

    async def _step_http_body_match(self, config: dict, timeout: int, pass_condition: dict) -> dict:
        url = config.get("url", "")
        method = config.get("method", "GET").upper()
        follow_redirects = config.get("follow_redirects", True)
        match_mode = pass_condition.get("mode", "contains")
        patterns = pass_condition.get("patterns", [])

        if not url:
            return {
                "success": False,
                "latency_ms": 0,
                "error_message": "URL not configured",
                "raw_response": None,
            }

        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=follow_redirects) as client:
                if method == "GET":
                    response = await client.get(url)
                elif method == "POST":
                    response = await client.post(url, json=config.get("body"))
                else:
                    response = await client.request(method, url)

                latency = (time.time() - start) * 1000
                body = response.text
                actual_code = str(response.status_code)

                match_success = False
                if match_mode == "contains":
                    match_success = all(p in body for p in patterns)
                elif match_mode == "contains_any":
                    match_success = any(p in body for p in patterns)
                elif match_mode == "regex":
                    match_success = all(re.search(p, body) for p in patterns)
                elif match_mode == "not_contains":
                    match_success = all(p not in body for p in patterns)
                else:
                    return {
                        "success": False,
                        "latency_ms": latency,
                        "error_message": f"Unknown match mode: {match_mode}",
                        "raw_response": body[:500],
                    }

                if match_success:
                    return {
                        "success": True,
                        "latency_ms": latency,
                        "error_message": None,
                        "raw_response": body[:500],
                    }
                else:
                    preview = body[:100] if body else "(empty body)"
                    return {
                        "success": False,
                        "latency_ms": latency,
                        "error_message": f"Body match failed (mode: {match_mode}, patterns: {patterns}). Body preview: {preview}",
                        "raw_response": body[:500],
                    }
        except httpx.TimeoutException:
            return {
                "success": False,
                "latency_ms": timeout * 1000,
                "error_message": "HTTP connection timeout",
                "raw_response": None,
            }
        except Exception as e:
            return {
                "success": False,
                "latency_ms": (time.time() - start) * 1000,
                "error_message": str(e),
                "raw_response": None,
            }

    async def _step_tcp_connect(self, config: dict, timeout: int, pass_condition: dict) -> dict:
        address = config.get("address", "")

        if not address:
            return {
                "success": False,
                "latency_ms": 0,
                "error_message": "Address not configured",
                "raw_response": None,
            }

        try:
            if ":" in address:
                host, port = address.rsplit(":", 1)
                port = int(port)
            else:
                return {
                    "success": False,
                    "latency_ms": 0,
                    "error_message": "Invalid address format (use host:port)",
                    "raw_response": None,
                }
        except ValueError:
            return {
                "success": False,
                "latency_ms": 0,
                "error_message": "Invalid port number",
                "raw_response": None,
            }

        start = time.time()
        try:
            def _connect():
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                try:
                    sock.connect((host, port))
                    sock.close()
                    return True, None
                except Exception as e:
                    return False, str(e)
                finally:
                    try:
                        sock.close()
                    except:
                        pass

            success, error = await asyncio.get_event_loop().run_in_executor(None, _connect)
            latency = (time.time() - start) * 1000

            if success:
                return {
                    "success": True,
                    "latency_ms": latency,
                    "error_message": None,
                    "raw_response": f"Connected to {host}:{port}",
                }
            else:
                return {
                    "success": False,
                    "latency_ms": latency,
                    "error_message": error or "Connection failed",
                    "raw_response": None,
                }
        except Exception as e:
            return {
                "success": False,
                "latency_ms": (time.time() - start) * 1000,
                "error_message": str(e),
                "raw_response": None,
            }

    async def _step_dns_resolve(self, config: dict, timeout: int, pass_condition: dict) -> dict:
        domain = config.get("domain", "")
        expected_ips = pass_condition.get("expected_ips", [])

        if not domain:
            return {
                "success": False,
                "latency_ms": 0,
                "error_message": "Domain not configured",
                "raw_response": None,
            }

        start = time.time()
        try:
            def _resolve():
                try:
                    import socket as _socket
                    results = _socket.getaddrinfo(domain, None)
                    ips = list(set([r[4][0] for r in results]))
                    return True, ips, None
                except Exception as e:
                    return False, [], str(e)

            success, ips, error = await asyncio.get_event_loop().run_in_executor(
                None, _resolve
            )
            latency = (time.time() - start) * 1000

            if not success:
                return {
                    "success": False,
                    "latency_ms": latency,
                    "error_message": error or "DNS resolution failed",
                    "raw_response": None,
                }

            if expected_ips:
                if any(ip in expected_ips for ip in ips):
                    return {
                        "success": True,
                        "latency_ms": latency,
                        "error_message": None,
                        "raw_response": f"Resolved to: {', '.join(ips)}",
                    }
                else:
                    return {
                        "success": False,
                        "latency_ms": latency,
                        "error_message": f"DNS result {ips} does not match expected {expected_ips}",
                        "raw_response": f"Resolved to: {', '.join(ips)}",
                    }
            else:
                return {
                    "success": True,
                    "latency_ms": latency,
                    "error_message": None,
                    "raw_response": f"Resolved to: {', '.join(ips)}",
                }
        except Exception as e:
            return {
                "success": False,
                "latency_ms": (time.time() - start) * 1000,
                "error_message": str(e),
                "raw_response": None,
            }

    async def _step_latency_threshold(self, config: dict, timeout: int, pass_condition: dict) -> dict:
        inner_step_type = config.get("step_type")
        inner_config = config.get("config", {})
        max_latency_ms = pass_condition.get("max_latency_ms", 1000)

        if not inner_step_type:
            return {
                "success": False,
                "latency_ms": 0,
                "error_message": "Inner step type not configured",
                "raw_response": None,
            }

        handler = getattr(self, f"_step_{inner_step_type}", None)
        if not handler:
            return {
                "success": False,
                "latency_ms": 0,
                "error_message": f"Unknown inner step type: {inner_step_type}",
                "raw_response": None,
            }

        result = await handler(inner_config, timeout, {})
        latency_ms = result.get("latency_ms") or 0

        if not result["success"]:
            return {
                "success": False,
                "latency_ms": latency_ms,
                "error_message": f"Inner probe failed: {result['error_message']}",
                "raw_response": result.get("raw_response"),
            }

        if latency_ms <= max_latency_ms:
            return {
                "success": True,
                "latency_ms": latency_ms,
                "error_message": None,
                "raw_response": f"Latency {latency_ms:.0f}ms <= threshold {max_latency_ms}ms",
            }
        else:
            return {
                "success": False,
                "latency_ms": latency_ms,
                "error_message": f"Latency {latency_ms:.0f}ms exceeded threshold {max_latency_ms}ms",
                "raw_response": result.get("raw_response"),
            }


rule_engine = RuleEngine()
