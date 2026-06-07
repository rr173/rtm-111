import { useMemo } from 'react';

const SEGMENT_COUNT = 60;
const TIME_WINDOW_MINUTES = 30;

function StatusTimeline({ results = [], interval = 30, silentStart = null, silentEnd = null, inSilentWindow = false }) {
  const segments = useMemo(() => {
    const now = Date.now();
    const windowMs = TIME_WINDOW_MINUTES * 60 * 1000;
    const segmentMs = windowMs / SEGMENT_COUNT;

    const statusBuckets = new Array(SEGMENT_COUNT).fill(null);
    const silentBuckets = new Array(SEGMENT_COUNT).fill(false);

    if (silentStart && silentEnd) {
      for (let i = 0; i < SEGMENT_COUNT; i++) {
        const segmentTime = new Date(now - i * segmentMs);
        silentBuckets[i] = _isInSilentWindow(segmentTime, silentStart, silentEnd);
      }
    }

    if (results.length === 0) {
      return statusBuckets.map((status, i) => ({ status, silent: silentBuckets[i] }));
    }

    const sortedResults = [...results].sort(
      (a, b) => new Date(b.timestamp) - new Date(a.timestamp)
    );

    let currentStatus = null;
    let currentBucketIdx = -1;

    for (const result of sortedResults) {
      const resultTime = new Date(result.timestamp).getTime();
      const bucketIdx = Math.floor((now - resultTime) / segmentMs);

      if (bucketIdx < 0 || bucketIdx >= SEGMENT_COUNT) continue;

      if (result.success) {
        currentStatus = 'healthy';
      } else {
        if (currentStatus === 'down' || !currentStatus) {
          currentStatus = 'down';
        } else {
          currentStatus = 'degraded';
        }
      }

      for (let i = bucketIdx; i <= currentBucketIdx && i < SEGMENT_COUNT; i++) {
        if (statusBuckets[i] === null) {
          statusBuckets[i] = currentStatus;
        }
      }
      currentBucketIdx = bucketIdx - 1;
      statusBuckets[bucketIdx] = currentStatus;
    }

    if (currentBucketIdx >= 0 && currentStatus) {
      for (let i = 0; i <= currentBucketIdx && i < SEGMENT_COUNT; i++) {
        if (statusBuckets[i] === null) {
          statusBuckets[i] = currentStatus;
        }
      }
    }

    return statusBuckets.map((status, i) => ({ status, silent: silentBuckets[i] }));
  }, [results, interval, silentStart, silentEnd]);

  return (
    <div className="timeline-container" title={`最近${TIME_WINDOW_MINUTES}分钟状态时间线`}>
      {segments.map((seg, idx) => (
        <div
          key={idx}
          className={`timeline-segment ${seg.status || 'no-data'} ${seg.silent ? 'silent-segment' : ''}`}
          title={seg.silent ? '静默时段' : ''}
        />
      ))}
    </div>
  );
}

function _isInSilentWindow(date, silentStart, silentEnd) {
  try {
    const [startH, startM] = silentStart.split(':').map(Number);
    const [endH, endM] = silentEnd.split(':').map(Number);
    const nowH = date.getHours();
    const nowM = date.getMinutes();

    const startTotal = startH * 60 + startM;
    const endTotal = endH * 60 + endM;
    const nowTotal = nowH * 60 + nowM;

    if (startTotal <= endTotal) {
      return startTotal <= nowTotal && nowTotal <= endTotal;
    } else {
      return nowTotal >= startTotal || nowTotal <= endTotal;
    }
  } catch (e) {
    return false;
  }
}

export default StatusTimeline;
