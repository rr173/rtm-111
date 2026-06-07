import { useMemo } from 'react';

const SEGMENT_COUNT = 60;
const TIME_WINDOW_MINUTES = 30;

function StatusTimeline({ results = [], interval = 30 }) {
  const segments = useMemo(() => {
    const now = Date.now();
    const windowMs = TIME_WINDOW_MINUTES * 60 * 1000;
    const segmentMs = windowMs / SEGMENT_COUNT;

    const buckets = new Array(SEGMENT_COUNT).fill(null);

    if (results.length === 0) {
      return buckets;
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
        if (buckets[i] === null) {
          buckets[i] = currentStatus;
        }
      }
      currentBucketIdx = bucketIdx - 1;
      buckets[bucketIdx] = currentStatus;
    }

    if (currentBucketIdx >= 0 && currentStatus) {
      for (let i = 0; i <= currentBucketIdx && i < SEGMENT_COUNT; i++) {
        if (buckets[i] === null) {
          buckets[i] = currentStatus;
        }
      }
    }

    return buckets;
  }, [results, interval]);

  return (
    <div className="timeline-container" title={`最近${TIME_WINDOW_MINUTES}分钟状态时间线`}>
      {segments.map((status, idx) => (
        <div
          key={idx}
          className={`timeline-segment ${status || 'no-data'}`}
        />
      ))}
    </div>
  );
}

export default StatusTimeline;
