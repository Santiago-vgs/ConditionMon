// A ranked bar list: label, bar, value. Deliberately a table/chart hybrid rather
// than a plain bar chart — PSI has 15 categories, and past roughly seven bins a
// pure chart blurs adjacent classes while the reader actually wants the numbers.
//
// One colour for the whole series (bar length already encodes magnitude; tinting
// darker-where-bigger would burn the colour channel re-stating it). The only
// exception is `threshold`, where crossing the line is a *state*, so the status
// colour is earned — and it never travels alone: flagged rows get a text label
// too, so the meaning survives colourblindness and greyscale printing.
export default function MetricBars({
  items,
  max,
  threshold,
  thresholdLabel,
  flagColor,
  barColor = "var(--accent)",
  format = (v) => v,
}) {
  const ceiling = max ?? Math.max(...items.map((i) => i.value)) * 1.1;

  return (
    <div className="bars">
      {/* The line lives in the same grid column as the bar tracks, so it lands
          exactly where a bar of that value would end. Positioning it against the
          container instead put it a gap-width off — visible as a bar of exactly
          0.250 not touching the 0.25 line. */}
      {threshold != null && (
        <div className="bars-threshold-col">
          <span
            className="bars-threshold"
            style={{ left: `${(threshold / ceiling) * 100}%` }}
          >
            <span className="bars-threshold-label">{thresholdLabel}</span>
          </span>
        </div>
      )}

      {items.map((item) => {
        const flagged = threshold != null && item.value > threshold;
        return (
          <div className="bar-row" key={item.label}>
            <span className="bar-label">{item.label}</span>
            <span className="bar-track">
              <span
                className="bar-mark"
                style={{
                  width: `${Math.max(1, (item.value / ceiling) * 100)}%`,
                  background: flagged ? flagColor : barColor,
                }}
              />
            </span>
            <span className={`bar-value${flagged ? " flagged" : ""}`}>
              {format(item.value)}
              {flagged && <span className="bar-flag">high</span>}
            </span>
          </div>
        );
      })}
    </div>
  );
}
