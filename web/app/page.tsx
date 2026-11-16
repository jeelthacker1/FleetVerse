import Link from "next/link";
import {
  ArrowUpRight,
  Boxes,
  Route,
  History,
  FlaskConical,
} from "lucide-react";
export default function Home() {
  return (
    <main className="landing">
      <nav>
        <Link className="brand" href="/">
          <Boxes />
          FleetVerse<span> / </span>
        </Link>
        <span className="eyebrow">WAREHOUSE INTELLIGENCE</span>
        <Link href="/console" className="button outline">
          Open mission control <ArrowUpRight size={16} />
        </Link>
      </nav>
      <section className="hero">
        <div className="eyebrow mint">
          <span className="dot" /> AUTONOMOUS SYSTEMS. OBSERVABLE DECISIONS.
        </div>
        <h1>
          Every robot.
          <br />
          Every decision.
          <br />
          <em>One living warehouse.</em>
        </h1>
        <p>
          Operate a simulated autonomous fleet. Rewind the moments that matter.
          Test the next move before it becomes an operational decision.
        </p>
        <Link href="/console" className="button primary">
          Enter mission control <ArrowUpRight size={18} />
        </Link>
        <span className="hero-note">
          Deterministic simulation · No paid services
        </span>
        <div
          className="hero-grid"
          aria-label="Illustrated warehouse architecture"
        >
          <div className="grid-label">
            FLEETVERSE / SYSTEM OVERVIEW <span>SIMULATED ENVIRONMENT</span>
          </div>
          <div className="architecture">
            <div>
              <Boxes />
              <b>Warehouse</b>
              <small>Layouts · stations · constraints</small>
            </div>
            <i>→</i>
            <div>
              <Route />
              <b>Simulation worker</b>
              <small>Routing · dispatch · reservations</small>
            </div>
            <i>→</i>
            <div>
              <History />
              <b>Event history</b>
              <small>Snapshots · decisions · telemetry</small>
            </div>
          </div>
          <footer>
            SERVER-AUTHORITATIVE STATE <span>POSTGRESQL + REDIS</span>
          </footer>
        </div>
      </section>
      <section className="features">
        {[
          [
            Route,
            "01 / Operate",
            "A fleet with real consequences",
            "Watch backend-computed routes, order state transitions and charging. Introduce failures and inspect the response.",
          ],
          [
            History,
            "02 / Investigate",
            "Go back to the decision",
            "Scrub recorded simulation snapshots. Inspect robot telemetry and the actual candidate scores behind dispatch.",
          ],
          [
            FlaskConical,
            "03 / Experiment",
            "Measure a different future",
            "Run paired seeded workloads with a different fleet or policy. Compare calculated results and export the evidence.",
          ],
        ].map(([Icon, label, title, text]) => {
          const I = Icon as typeof Route;
          return (
            <article key={String(label)}>
              <I />
              <small>{String(label)}</small>
              <h2>{String(title)}</h2>
              <p>{String(text)}</p>
            </article>
          );
        })}
      </section>
      <footer className="landing-footer">
        FleetVerse / Open engineering, observable operations.
        <span>All robot activity is simulated.</span>
      </footer>
    </main>
  );
}
