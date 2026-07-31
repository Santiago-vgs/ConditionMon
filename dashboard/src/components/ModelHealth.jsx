import { useEffect, useState } from "react";
import { fetchMetrics } from "../api";
import { PSI_THRESHOLD, STATUS } from "../config";
import CostSweepChart from "./CostSweepChart";
import MetricBars from "./MetricBars";

// The evaluation suite in insights.py, surfaced. These numbers decide whether
// the fleet view is worth believing — coverage, where the error actually lives,
// whether the alert policy would have caught the failures, and whether incoming
// data still resembles what the model trained on. They existed before this view
// did, but only inside a markdown file nobody opens.
export default function ModelHealth() {
  const [metrics, setMetrics] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetchMetrics()
      .then((d) => !cancelled && setMetrics(d))
      .catch((e) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return <p className="msg error">Couldn’t load metrics — {error}</p>;
  }
  if (!metrics) return <p className="msg">Loading metrics…</p>;

  const { conformal, backtest, rmse_by_band, psi, threshold_sweep } = metrics;
  const coveragePct = Math.round(conformal.coverage * 100);

  const psiItems = Object.entries(psi)
    .sort((a, b) => b[1] - a[1])
    .map(([sensor, value]) => ({ label: sensor.replace("sensor_", "Sensor "), value }));

  const rmseItems = Object.entries(rmse_by_band).map(([band, value]) => ({
    label: `RUL ${band.replace("-", "–")}`,
    value,
  }));

  const driftCount = psiItems.filter((i) => i.value > PSI_THRESHOLD).length;

  return (
    <div className="health">
      <section className="health-section">
        <h2 className="section">Prediction quality</h2>
        <div className="tiles">
          <Tile
            value={`${coveragePct}%`}
            label="Interval coverage"
            note={`Target 90% · measured on ${metrics.n_test_engines} unseen engines`}
            good={coveragePct >= 88 && coveragePct <= 96}
          />
          <Tile
            value={conformal.mean_width_critical}
            label="Interval width near failure"
            note={`vs ${conformal.mean_width_healthy} cycles when healthy`}
          />
          <Tile
            value={(metrics.phm08_total / metrics.n_test_engines).toFixed(1)}
            label="PHM08 score per engine"
            note="NASA metric · penalises late calls ~3× harder · lower is better"
          />
        </div>

        <h3 className="subhead">Error by true RUL band</h3>
        <p className="note">
          One global RMSE hides where the model is useful. It is sharpest near
          failure, which is the region the alerting policy actually reads.
        </p>
        <MetricBars
          items={rmseItems}
          format={(v) => `${v.toFixed(1)} cyc`}
        />
      </section>

      <section className="health-section">
        <h2 className="section">Alerting policy</h2>
        <div className="tiles">
          <Tile
            value={`${backtest.caught}/${backtest.n}`}
            label="Failures caught in backtest"
            note={`At τ=${backtest.tau}, replayed over full engine lives`}
            good={backtest.caught === backtest.n}
          />
          <Tile
            value={backtest.median_lead}
            label="Median lead time (cycles)"
            note={`Range ${backtest.min_lead}–${backtest.max_lead} · ${metrics.min_actionable_lead} needed to act`}
          />
        </div>

        <h3 className="subhead">Choosing τ by cost</h3>
        <CostSweepChart
          taus={threshold_sweep.taus}
          ratios={threshold_sweep.ratios}
        />
      </section>

      <section className="health-section">
        <h2 className="section">Data drift</h2>
        <p className="note">
          Population Stability Index between the training and test sensor
          distributions. {driftCount} of {psiItems.length} sensors sit above the
          conventional {PSI_THRESHOLD} investigate line. On C-MAPSS this is
          expected — test engines are sampled mid-life rather than run to
          failure, so their readings skew healthy — but in production this is the
          panel that should gate a retrain.
        </p>
        <MetricBars
          items={psiItems}
          threshold={PSI_THRESHOLD}
          thresholdLabel={`${PSI_THRESHOLD} investigate`}
          flagColor={STATUS.WARNING.color}
          format={(v) => v.toFixed(3)}
        />
      </section>

      <p className="health-footnote">
        Computed by <code>src/insights.py</code> over the held-out validation
        engines and the 100-engine test set, and republished with each pipeline
        run. These are offline evaluation figures on a fixed public dataset — not
        live production monitoring.
      </p>
    </div>
  );
}

function Tile({ value, label, note, good }) {
  return (
    <div className="tile">
      <div className="tile-value" style={good ? { color: STATUS.OK.color } : undefined}>
        {value}
      </div>
      <div className="tile-label">{label}</div>
      {note && <div className="tile-note">{note}</div>}
    </div>
  );
}
