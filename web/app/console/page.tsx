"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  Activity,
  ArrowUpRight,
  Boxes,
  ChevronRight,
  FlaskConical,
  History,
  LayoutGrid,
  LogOut,
  Play,
  Radio,
  Settings,
  Shield,
  Square,
  Pause,
  RotateCcw,
  Zap,
} from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Button } from "@/components/ui/button";
import { WarehouseMap } from "@/components/warehouse-map";
import { api, API, useFleet } from "@/lib/api";
import type {
  Cell,
  ExperimentResult,
  Layout,
  LayoutRecord,
  Payload,
  SimEvent,
  User,
} from "@/lib/types";

type Tab =
  | "Mission control"
  | "Warehouse designer"
  | "Incident time machine"
  | "What-if laboratory"
  | "Administration";
const tabs = [
  [Activity, "Mission control"],
  [LayoutGrid, "Warehouse designer"],
  [History, "Incident time machine"],
  [FlaskConical, "What-if laboratory"],
  [Shield, "Administration"],
] as const;
const fmt = (value: number | undefined) =>
  (value || 0).toLocaleString(undefined, { maximumFractionDigits: 1 });

export default function Console() {
  const { user, setUser, live, setLive, connection, setConnection } =
    useFleet();
  const [ready, setReady] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [tab, setTab] = useState<Tab>("Mission control"),
    [layouts, setLayouts] = useState<LayoutRecord[]>([]),
    [layoutId, setLayoutId] = useState(1);
  const [runs, setRuns] = useState<
      { id: number; tick: number; status: string }[]
    >([]),
    [runId, setRunId] = useState<number | null>(null),
    [fleet, setFleet] = useState(20),
    [seed, setSeed] = useState(42);
  const [selected, setSelected] = useState("R01"),
    [cell, setCell] = useState<Cell>([2, 2]),
    [paths, setPaths] = useState(true),
    [busy, setBusy] = useState(false);
  const [historical, setHistorical] = useState<Payload | null>(null),
    [historyTick, setHistoryTick] = useState(0),
    [playing, setPlaying] = useState(false),
    [replaySpeed, setReplaySpeed] = useState(1),
    [filter, setFilter] = useState("all");
  const [events, setEvents] = useState<SimEvent[]>([]),
    [draft, setDraft] = useState<Layout | null>(null),
    [tool, setTool] = useState("blocked"),
    [layoutName, setLayoutName] = useState("Custom warehouse");
  const [experimentId, setExperimentId] = useState<number | null>(null),
    [result, setResult] = useState<ExperimentResult | null>(null),
    [expStatus, setExpStatus] = useState(""),
    [expFleet, setExpFleet] = useState(25),
    [policy, setPolicy] = useState("improved"),
    [removeCharger, setRemoveCharger] = useState(false),
    [expBlock, setExpBlock] = useState(false),
    [arrival, setArrival] = useState(0),
    [expPriority, setExpPriority] = useState(2);
  const [audit, setAudit] = useState<
      { id: number; action: string; created: string }[]
    >([]),
    [users, setUsers] = useState<
      { id: number; username: string; role: string }[]
    >([]);
  const [pickup, setPickup] = useState(0),
    [dropoff, setDropoff] = useState(0),
    [priority, setPriority] = useState(2),
    [orderId, setOrderId] = useState("");
  const canOperate = user?.role !== "VIEWER",
    isAdmin = user?.role === "ADMIN";
  const liveRef = useRef(live);
  liveRef.current = live;
  const act = useCallback(async (fn: () => Promise<void>) => {
    setError("");
    setBusy(true);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, []);
  const refresh = useCallback(async () => {
    const [ls, rs] = await Promise.all([
      api<LayoutRecord[]>("/layouts"),
      api<{ id: number; tick: number; status: string }[]>("/simulations"),
    ]);
    setLayouts(ls);
    setRuns(rs);
    if (ls.length) {
      setLayoutId(ls[0].id);
      setDraft(structuredClone(ls[0].data));
    }
    if (rs.length) setRunId((current) => current || rs[0].id);
  }, []);
  useEffect(() => {
    api<User>("/auth/me")
      .then(setUser)
      .catch(() => {})
      .finally(() => setReady(true));
  }, [setUser]);
  useEffect(() => {
    if (user) void act(refresh);
  }, [user, act, refresh]);
  useEffect(() => {
    if (!user || !runId) return;
    let closed = false,
      socket: WebSocket | undefined,
      timer: ReturnType<typeof setTimeout>;
    let retries = 0;
    const connect = () => {
      if (closed) return;
      setConnection("connecting");
      socket = new WebSocket(
        `${API.replace(/^http/, "ws")}/api/v1/ws/${runId}`,
      );
      socket.onopen = () => {
        retries = 0;
        setConnection("live");
      };
      socket.onmessage = (e) => {
        const p = JSON.parse(e.data);
        if (p.state) setLive(p);
      };
      socket.onclose = () => {
        if (closed) return;
        setConnection("reconnecting");
        timer = setTimeout(connect, Math.min(10000, 500 * 2 ** retries++));
      };
      socket.onerror = () => socket?.close();
    };
    api<Payload>(`/simulations/${runId}`)
      .then((p) => {
        if (!closed) setLive(p);
      })
      .catch((e) => setError(String(e)));
    connect();
    return () => {
      closed = true;
      clearTimeout(timer);
      socket?.close();
    };
  }, [user, runId, setLive, setConnection]);
  useEffect(() => {
    if (tab === "Incident time machine" && runId) {
      api<SimEvent[]>(`/simulations/${runId}/events`)
        .then(setEvents)
        .catch((e) => setError(String(e)));
    }
  }, [tab, runId, live?.revision]);
  useEffect(() => {
    if (tab !== "Incident time machine" || !runId) return;
    let active = true;
    api<Payload>(`/simulations/${runId}/history/${historyTick}`)
      .then((p) => {
        if (active) setHistorical(p);
      })
      .catch((e) => setError(String(e)));
    return () => {
      active = false;
    };
  }, [tab, runId, historyTick]);
  useEffect(() => {
    if (!playing) return;
    const id = setInterval(
      () =>
        setHistoryTick((t) => {
          const end = liveRef.current?.state.tick || 0;
          if (t >= end) {
            setPlaying(false);
            return end;
          }
          return t + 1;
        }),
      500 / replaySpeed,
    );
    return () => clearInterval(id);
  }, [playing, replaySpeed]);
  useEffect(() => {
    if (!experimentId || expStatus !== "pending") return;
    const id = setInterval(() => {
      api<{
        status: string;
        error: string | null;
        result: ExperimentResult | null;
      }>(`/experiments/${experimentId}`)
        .then((v) => {
          setExpStatus(v.status);
          if (v.result) setResult(v.result);
          if (v.error) setError(v.error);
        })
        .catch((e) => setError(String(e)));
    }, 1000);
    return () => clearInterval(id);
  }, [experimentId, expStatus]);
  useEffect(() => {
    if (tab === "Administration" && isAdmin)
      void act(async () => {
        const [a, u] = await Promise.all([
          api<typeof audit>("/audit"),
          api<typeof users>("/users"),
        ]);
        setAudit(a);
        setUsers(u);
      });
  }, [tab, isAdmin, act]);
  const send = async (kind: string, data: Record<string, unknown> = {}) => {
    if (!runId) return;
    const c = await api<{ id: number; status: string; error: string | null }>(
      `/simulations/${runId}/commands`,
      { kind, data },
    );
    let status = c;
    for (let i = 0; status.status === "pending" && i < 50; i++) {
      await new Promise((r) => setTimeout(r, 200));
      status = await api(`/commands/${c.id}`);
    }
    if (status.status === "rejected")
      throw new Error(status.error || "Command rejected");
    setNotice(
      status.status === "applied"
        ? `${kind.replaceAll("_", " ")} applied`
        : `Command ${c.id} is queued; worker has not acknowledged it yet.`,
    );
  };
  const displayed = tab === "Incident time machine" ? historical : live;
  const state = displayed?.state,
    stats = displayed?.metrics;
  const robot = state?.robots.find((r) => r.id === selected);
  const order = state?.orders.find((o) => o.id === orderId);
  const selectLayout = (id: number) => {
    setLayoutId(id);
    const found = layouts.find((l) => l.id === id);
    if (found) {
      setDraft(structuredClone(found.data));
      setLayoutName(found.name + " / revision");
    }
  };
  const paint = (p: Cell) => {
    setCell(p);
    if (!draft || !isAdmin) return;
    const next = structuredClone(draft);
    for (const k of [
      "blocked",
      "restricted",
      "pickup",
      "dropoff",
      "chargers",
      "checkpoints",
    ] as const)
      next[k] = next[k].filter((c) => c[0] !== p[0] || c[1] !== p[1]);
    delete next.lanes[p.join(",")];
    if (tool.startsWith("lane")) next.lanes[p.join(",")] = tool.slice(-1);
    else if (tool !== "erase") next[tool as "blocked"].push(p);
    setDraft(next);
  };
  if (!ready) return <div className="loading">Connecting to FleetVerse…</div>;
  if (!user)
    return (
      <main className="login">
        <Link href="/" className="brand">
          <Boxes /> FleetVerse /
        </Link>
        <div className="login-card">
          <span className="eyebrow mint">OPERATIONS ACCESS</span>
          <h1>
            Welcome to
            <br />
            mission control.
          </h1>
          <p>Sign in to your simulated warehouse environment.</p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const data = new FormData(e.currentTarget);
              void act(async () =>
                setUser(
                  await api<User>("/auth/login", {
                    username: data.get("username"),
                    password: data.get("password"),
                  }),
                ),
              );
            }}
          >
            <label>
              Username
              <input
                name="username"
                autoComplete="username"
                required
                defaultValue="admin"
              />
            </label>
            <label>
              Password
              <input
                name="password"
                type="password"
                autoComplete="current-password"
                required
              />
            </label>
            <Button disabled={busy}>
              Sign in <ArrowUpRight size={16} />
            </Button>
          </form>
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
          <small>
            Explicit demo mode only: admin / operator / viewer
            <br />
            Password: fleetverse-demo
          </small>
        </div>
        <footer>SIMULATED OPERATIONS · SERVER-AUTHORITATIVE TELEMETRY</footer>
      </main>
    );
  return (
    <div className="shell">
      <aside className="sidebar">
        <Link className="brand" href="/">
          <Boxes />
          FleetVerse<span>/</span>
        </Link>
        <div className="workspace">
          <span className="workspace-icon">N</span>
          <div>
            Northstar logistics<small>Simulation workspace</small>
          </div>
          <ChevronRight size={14} />
        </div>
        <div className="nav-label">WORKSPACE</div>
        <nav>
          {tabs
            .filter(([, name]) => name !== "Administration" || isAdmin)
            .map(([Icon, name]) => (
              <button
                key={name}
                className={tab === name ? "active" : ""}
                onClick={() => {
                  setTab(name);
                  setPlaying(false);
                }}
              >
                <Icon size={18} />
                {name}
              </button>
            ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="system-card">
            <span className="dot" /> SIMULATION ENVIRONMENT
            <p>
              Every metric comes from
              <br />
              the simulation worker.
            </p>
          </div>
          <div className="user">
            <span className="avatar">{user.username[0].toUpperCase()}</span>
            <div>
              {user.username}
              <small>{user.role}</small>
            </div>
            <button
              aria-label="Sign out"
              onClick={() =>
                void act(async () => {
                  await api("/auth/logout", {});
                  setUser(null);
                })
              }
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <span>
            Workspace <ChevronRight size={12} /> <b>{tab}</b>
          </span>
          <span className="connection">
            <i className={`dot ${connection !== "live" ? "amber" : ""}`} />
            {connection === "live" ? "Stream connected" : connection}
            <span className="separator">/</span>
            <span className="sim-badge">SIMULATED</span>
          </span>
        </header>
        <div className="content">
          <div className="page-title">
            <div>
              <div className="eyebrow">
                OPERATIONS /{" "}
                {tab === "Mission control"
                  ? "LIVE OVERVIEW"
                  : tab === "Incident time machine"
                    ? "RECORDED HISTORY"
                    : tab === "What-if laboratory"
                      ? "COUNTERFACTUAL ANALYSIS"
                      : "CONFIGURATION"}
              </div>
              <h1>
                {tab}
                <span className="title-dot">.</span>
              </h1>
              <p>
                {tab === "Mission control"
                  ? "Your entire fleet. One operational picture."
                  : tab === "Warehouse designer"
                    ? "Define the space. Validate the constraints. Save a new layout."
                    : tab === "Incident time machine"
                      ? "Inspect recorded states without altering the live simulation."
                      : tab === "What-if laboratory"
                        ? "Change one assumption. Measure the operational difference."
                        : "Manage access and inspect the audit trail."}
              </p>
            </div>
            <div className="run-selector">
              <label>
                ACTIVE RUN
                <select
                  value={runId || ""}
                  onChange={(e) => setRunId(Number(e.target.value))}
                >
                  <option value="" disabled>
                    Select a run
                  </option>
                  {runs.map((r) => (
                    <option key={r.id} value={r.id}>
                      Run #{r.id}
                    </option>
                  ))}
                </select>
              </label>
              <span className="tick">
                T+{String(live?.state.tick || 0).padStart(5, "0")}
              </span>
            </div>
          </div>
          {error && (
            <div className="error banner" role="alert">
              {error}
              <button onClick={() => setError("")}>Dismiss</button>
            </div>
          )}
          {notice && (
            <div className="notice banner" role="status">
              {notice}
              <button onClick={() => setNotice("")}>Dismiss</button>
            </div>
          )}
          {(!runId || tab === "Warehouse designer") && (
            <section className="panel setup">
              <div>
                <h2>Launch a simulation</h2>
                <p>
                  Choose a saved warehouse and a reproducible workload seed.
                </p>
              </div>
              <label>
                Layout
                <select
                  value={layoutId}
                  onChange={(e) => selectLayout(Number(e.target.value))}
                >
                  {layouts.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Robots
                <input
                  type="number"
                  min={1}
                  max={80}
                  value={fleet}
                  onChange={(e) => setFleet(Number(e.target.value))}
                />
              </label>
              <label>
                Seed
                <input
                  type="number"
                  min={0}
                  value={seed}
                  onChange={(e) => setSeed(Number(e.target.value))}
                />
              </label>
              <Button
                disabled={!isAdmin || busy}
                onClick={() =>
                  void act(async () => {
                    const r = await api<{ id: number }>("/simulations", {
                      layout_id: layoutId,
                      fleet,
                      seed,
                    });
                    await refresh();
                    setRunId(r.id);
                    setTab("Mission control");
                    setNotice(
                      "Simulation created. Generate orders, then start.",
                    );
                  })
                }
              >
                Create simulation <Play size={14} />
              </Button>
            </section>
          )}
          {tab === "Mission control" && state && (
            <>
              <section className="metrics">
                {[
                  ["Completed deliveries", stats?.completed, "deliveries"],
                  ["Fleet utilization", stats?.utilization, "% active ticks"],
                  [
                    "Average delivery",
                    stats?.average_duration,
                    "simulated seconds",
                  ],
                  ["Throughput", stats?.throughput, "deliveries / sim. hour"],
                ].map(([name, value, unit]) => (
                  <article key={String(name)}>
                    <span>{name}</span>
                    <strong>{fmt(Number(value))}</strong>
                    <small>{unit}</small>
                  </article>
                ))}
              </section>
              <div className="operations-grid">
                <section className="panel map-panel">
                  <div className="panel-head">
                    <div>
                      <h2>
                        <span className="dot" /> Warehouse live view
                      </h2>
                      <small>
                        {state.layout.name} <span>/</span> {state.robots.length}{" "}
                        robots
                      </small>
                    </div>
                    <span className="badge">{state.status.toUpperCase()}</span>
                  </div>
                  <div className="map-controls">
                    <Button
                      variant="outline"
                      disabled={!canOperate || busy}
                      onClick={() =>
                        void act(() =>
                          send(state.status === "running" ? "pause" : "start"),
                        )
                      }
                    >
                      {state.status === "running" ? (
                        <Pause size={14} />
                      ) : (
                        <Play size={14} />
                      )}{" "}
                      {state.status === "running" ? "Pause" : "Start"}
                    </Button>
                    <Button
                      variant="ghost"
                      disabled={!canOperate || busy}
                      onClick={() => void act(() => send("stop"))}
                    >
                      <Square size={13} />
                      Stop
                    </Button>
                    <Button
                      variant="ghost"
                      disabled={!isAdmin || busy}
                      onClick={() => void act(() => send("reset"))}
                    >
                      <RotateCcw size={14} />
                      Reset
                    </Button>
                    <label className="inline">
                      Speed
                      <select
                        aria-label="Simulation speed"
                        value={state.speed}
                        onChange={(e) =>
                          void act(() =>
                            send("speed", { value: Number(e.target.value) }),
                          )
                        }
                        disabled={!canOperate}
                      >
                        {[0.5, 1, 2, 4, 8].map((n) => (
                          <option key={n} value={n}>
                            {n}×
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="inline">
                      <input
                        type="checkbox"
                        checked={paths}
                        onChange={(e) => setPaths(e.target.checked)}
                      />{" "}
                      Paths
                    </label>
                  </div>
                  <WarehouseMap
                    layout={state.layout}
                    state={state}
                    selected={selected}
                    onRobot={setSelected}
                    onCell={setCell}
                    paths={paths}
                  />
                  <div className="map-legend">
                    <span>
                      <i className="legend-dot mint-bg" />
                      Robot
                    </span>
                    <span>
                      <i className="legend-dot blue-bg" />
                      Pickup
                    </span>
                    <span>
                      <i className="legend-dot amber-bg" />
                      Drop-off
                    </span>
                    <span>
                      <Zap size={12} />
                      Charging
                    </span>
                    <span className="coordinates">
                      Selected cell {cell.join(" : ")}
                    </span>
                  </div>
                </section>
                <section className="panel telemetry">
                  <div className="panel-head">
                    <h2>Robot telemetry</h2>
                    <Radio size={16} />
                  </div>
                  {robot && (
                    <>
                      <div className="robot-heading">
                        <span className="robot-avatar">
                          <Boxes size={26} />
                        </span>
                        <div>
                          <h3>{robot.id}</h3>
                          <span className="mint">
                            {robot.state.replaceAll("_", " ")}
                          </span>
                        </div>
                        <span className="badge">LIVE</span>
                      </div>
                      <div className="battery">
                        <span>
                          Battery health <b>{fmt(robot.battery)}%</b>
                        </span>
                        <div>
                          <i style={{ width: `${robot.battery}%` }} />
                        </div>
                      </div>
                      <dl>
                        {[
                          ["Position", robot.pos.join(", ")],
                          ["Destination", robot.destination?.join(", ") || "—"],
                          ["Assigned order", robot.task || "Unassigned"],
                          [
                            "Load / capacity",
                            `${robot.load} / ${robot.capacity}`,
                          ],
                          ["Travel distance", `${robot.distance} cells`],
                          ["Completed", robot.completed],
                          ["Waiting", `${robot.wait} ticks`],
                          [
                            "Failure history",
                            robot.failures.join(", ") || "None",
                          ],
                        ].map(([k, v]) => (
                          <div key={k}>
                            <dt>{k}</dt>
                            <dd>{v}</dd>
                          </div>
                        ))}
                      </dl>
                      <div className="telemetry-actions">
                        <Button
                          variant="outline"
                          disabled={!canOperate || busy}
                          onClick={() =>
                            void act(() =>
                              send("breakdown", { robot: selected }),
                            )
                          }
                        >
                          Inject breakdown
                        </Button>
                        <Button
                          variant="outline"
                          disabled={!canOperate || busy}
                          onClick={() =>
                            void act(() =>
                              send("low_battery", { robot: selected }),
                            )
                          }
                        >
                          Low battery
                        </Button>
                        <Button
                          variant="outline"
                          disabled={!canOperate || busy}
                          onClick={() =>
                            void act(() => send("recover", { robot: selected }))
                          }
                        >
                          Recover robot
                        </Button>
                      </div>
                    </>
                  )}
                </section>
              </div>
              <section className="panel incident-bar">
                <div>
                  <Zap size={19} />
                  <h2>Failure injection</h2>
                  <small>Real changes to simulated operations</small>
                </div>
                <select
                  id="failure"
                  aria-label="Failure type"
                  defaultValue="block"
                >
                  <option value="block">Block selected cell</option>
                  <option value="unblock">Clear selected cell</option>
                  <option value="charger_failure">Fail selected charger</option>
                  <option value="charger_restore">
                    Restore selected charger
                  </option>
                  <option value="station_failure">
                    Close selected drop-off
                  </option>
                  <option value="station_restore">
                    Reopen selected drop-off
                  </option>
                  <option value="urgent">Urgent order</option>
                  <option value="surge">20-order surge</option>
                </select>
                <Button
                  variant="outline"
                  disabled={!canOperate || busy}
                  onClick={() =>
                    void act(() =>
                      send(
                        (
                          document.getElementById(
                            "failure",
                          ) as HTMLSelectElement
                        ).value,
                        { cell, count: 20 },
                      ),
                    )
                  }
                >
                  Inject event <Zap size={14} />
                </Button>
              </section>
              <div className="lower-grid">
                <section className="panel">
                  <div className="panel-head">
                    <h2>
                      Delivery queue{" "}
                      <span className="count">{state.orders.length}</span>
                    </h2>
                    <Button
                      variant="outline"
                      disabled={!canOperate || busy}
                      onClick={() =>
                        void act(() => send("generate", { count: 20 }))
                      }
                    >
                      Generate 20 orders
                    </Button>
                  </div>
                  <form
                    className="order-form"
                    onSubmit={(e) => {
                      e.preventDefault();
                      void act(() =>
                        send("order", {
                          pickup: state.layout.pickup[pickup],
                          dropoff: state.layout.dropoff[dropoff],
                          priority,
                        }),
                      );
                    }}
                  >
                    <label>
                      Pickup
                      <select
                        value={pickup}
                        onChange={(e) => setPickup(Number(e.target.value))}
                      >
                        {state.layout.pickup.map((p, i) => (
                          <option value={i} key={i}>
                            P{i + 1} ({p.join(",")})
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Drop-off
                      <select
                        value={dropoff}
                        onChange={(e) => setDropoff(Number(e.target.value))}
                      >
                        {state.layout.dropoff.map((p, i) => (
                          <option value={i} key={i}>
                            D{i + 1} ({p.join(",")})
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Priority
                      <select
                        value={priority}
                        onChange={(e) => setPriority(Number(e.target.value))}
                      >
                        {[1, 2, 3, 4, 5].map((p) => (
                          <option key={p}>{p}</option>
                        ))}
                      </select>
                    </label>
                    <Button disabled={!canOperate || busy}>Create order</Button>
                  </form>
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>ORDER</th>
                          <th>ROBOT</th>
                          <th>STATUS</th>
                          <th>ETA / TICK</th>
                          <th />
                        </tr>
                      </thead>
                      <tbody>
                        {state.orders
                          .slice(-60)
                          .reverse()
                          .map((o) => (
                            <tr
                              key={o.id}
                              onClick={() => {
                                setOrderId(o.id);
                                if (o.robot) setSelected(o.robot);
                              }}
                            >
                              <td>
                                <button className="text-button">{o.id}</button>
                              </td>
                              <td>{o.robot || "—"}</td>
                              <td>
                                <span
                                  className={`status ${o.status === "COMPLETED" ? "mint" : ""}`}
                                >
                                  {o.status.replaceAll("_", " ")}
                                </span>
                              </td>
                              <td>{o.finished ?? o.eta ?? "Queued"}</td>
                              <td>
                                {!["COMPLETED", "CANCELLED"].includes(
                                  o.status,
                                ) && (
                                  <button
                                    className="text-button"
                                    disabled={!canOperate || busy}
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      void act(() =>
                                        send("cancel", { id: o.id }),
                                      );
                                    }}
                                  >
                                    Cancel
                                  </button>
                                )}
                              </td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                    {!state.orders.length && (
                      <div className="empty">
                        No orders yet. Generate a workload or create a delivery.
                      </div>
                    )}
                  </div>
                  {order && (
                    <div className="order-detail">
                      <b>{order.id} / state transitions</b>
                      <p>
                        {order.history
                          .map((h) => `${h.status} @ ${h.tick}`)
                          .join(" → ")}
                      </p>
                      {order.status === "QUEUED" && (
                        <Button
                          variant="outline"
                          disabled={!canOperate || busy}
                          onClick={() =>
                            void act(() =>
                              send("assign", { id: order.id, robot: selected }),
                            )
                          }
                        >
                          Assign to {selected}
                        </Button>
                      )}
                    </div>
                  )}
                </section>
                <section className="panel">
                  <div className="panel-head">
                    <h2>Operations timeline</h2>
                    <button
                      className="text-button"
                      onClick={() => setTab("Incident time machine")}
                    >
                      View history ↗
                    </button>
                  </div>
                  <div className="timeline">
                    {state.events
                      .slice(-12)
                      .reverse()
                      .map((e) => (
                        <div key={e.seq}>
                          <i
                            className={`dot ${e.kind === "incident" ? "amber" : ""}`}
                          />
                          <div>
                            <span>{e.message}</span>
                            <small>
                              T+{e.tick} / {e.kind}
                            </small>
                          </div>
                        </div>
                      ))}
                    {!state.events.length && (
                      <p className="empty">
                        Events appear when commands are applied.
                      </p>
                    )}
                  </div>
                </section>
              </div>
              <section className="secondary-metrics">
                {[
                  ["On-time deliveries", `${fmt(stats?.on_time)}%`],
                  ["Travel distance", `${fmt(stats?.travel_distance)} cells`],
                  ["Congestion waits", fmt(stats?.congestion)],
                  ["Collision violations", fmt(stats?.collision_violations)],
                  ["Battery consumed", `${fmt(stats?.battery_consumption)} pp`],
                  ["Idle time", `${fmt(stats?.idle_time)} robot-ticks`],
                ].map(([k, v]) => (
                  <div key={k}>
                    <small>{k}</small>
                    <b>{v}</b>
                  </div>
                ))}
              </section>
            </>
          )}
          {tab === "Warehouse designer" && draft && (
            <section className="panel">
              <div className="panel-head">
                <h2>Layout canvas</h2>
                <span className="badge">
                  EDIT COPY · SAVED RUNS ARE IMMUTABLE
                </span>
              </div>
              <div className="designer-tools">
                <label>
                  Paint tool
                  <select
                    value={tool}
                    onChange={(e) => setTool(e.target.value)}
                  >
                    {[
                      "blocked",
                      "restricted",
                      "pickup",
                      "dropoff",
                      "chargers",
                      "checkpoints",
                      "lane N",
                      "lane S",
                      "lane E",
                      "lane W",
                      "erase",
                    ].map((t) => (
                      <option key={t}>{t}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Name
                  <input
                    value={layoutName}
                    onChange={(e) => setLayoutName(e.target.value)}
                  />
                </label>
                <label>
                  Width
                  <input
                    type="number"
                    min={8}
                    max={60}
                    value={draft.width}
                    onChange={(e) =>
                      setDraft({ ...draft, width: Number(e.target.value) })
                    }
                  />
                </label>
                <label>
                  Height
                  <input
                    type="number"
                    min={8}
                    max={60}
                    value={draft.height}
                    onChange={(e) =>
                      setDraft({ ...draft, height: Number(e.target.value) })
                    }
                  />
                </label>
                <Button
                  disabled={!isAdmin || busy}
                  onClick={() =>
                    void act(async () => {
                      await api("/layouts", {
                        name: layoutName,
                        warehouse_id:
                          layouts.find((l) => l.id === layoutId)
                            ?.warehouse_id || 1,
                        data: { ...draft, name: layoutName },
                      });
                      await refresh();
                      setNotice(
                        "Layout validated and saved. Select it to create a simulation.",
                      );
                    })
                  }
                >
                  Validate & save
                </Button>
              </div>
              <WarehouseMap layout={draft} onCell={paint} />
              <p className="panel-note">
                Click a cell to paint. Erase the old cell and paint a new one to
                move a rack or station. Directional arrows constrain exits.
                Validation checks station reachability and overlapping cells.
              </p>
              <form
                className="order-form"
                onSubmit={(e) => {
                  e.preventDefault();
                  const f = new FormData(e.currentTarget);
                  void act(async () => {
                    const w = await api<{ id: number }>("/warehouses", {
                      name: f.get("name"),
                    });
                    await api("/layouts", {
                      name: layoutName,
                      warehouse_id: w.id,
                      data: { ...draft, name: layoutName },
                    });
                    await refresh();
                    setNotice("Warehouse and layout created.");
                  });
                }}
              >
                <label>
                  New warehouse name
                  <input
                    name="name"
                    required
                    placeholder="West distribution center"
                  />
                </label>
                <Button variant="outline" disabled={!isAdmin || busy}>
                  Create warehouse with this layout
                </Button>
              </form>
            </section>
          )}
          {tab === "Incident time machine" && live && (
            <>
              <section className="panel replay">
                <div>
                  <span className="badge amber-text">RECORDED HISTORY</span>
                  <h2>
                    Tick {historyTick} <small>of {live.state.tick}</small>
                  </h2>
                </div>
                <Button variant="outline" onClick={() => setPlaying(!playing)}>
                  {playing ? <Pause size={14} /> : <Play size={14} />}{" "}
                  {playing ? "Pause replay" : "Play replay"}
                </Button>
                <select
                  aria-label="Replay speed"
                  value={replaySpeed}
                  onChange={(e) => setReplaySpeed(Number(e.target.value))}
                >
                  {[0.5, 1, 2, 4].map((v) => (
                    <option key={v} value={v}>
                      {v}×
                    </option>
                  ))}
                </select>
                <input
                  aria-label="History tick"
                  type="range"
                  min={0}
                  max={live.state.tick}
                  value={historyTick}
                  onChange={(e) => {
                    setPlaying(false);
                    setHistoryTick(Number(e.target.value));
                  }}
                />
                <b>T+{historyTick}</b>
              </section>
              <div className="operations-grid">
                <section className="panel">
                  {state && (
                    <WarehouseMap
                      layout={state.layout}
                      state={state}
                      selected={selected}
                      onRobot={setSelected}
                    />
                  )}
                </section>
                <section className="panel history-info">
                  <h2>State comparison</h2>
                  <p>
                    Recorded tick {state?.tick} → live tick {live.state.tick}
                  </p>
                  <dl>
                    {[
                      "completed",
                      "travel_distance",
                      "congestion",
                      "battery_consumption",
                    ].map((k) => (
                      <div key={k}>
                        <dt>{k.replaceAll("_", " ")}</dt>
                        <dd>
                          {fmt(stats?.[k])} → {fmt(live.metrics[k])}
                        </dd>
                      </div>
                    ))}
                  </dl>
                  {robot && (
                    <>
                      <h3>{robot.id} at recorded tick</h3>
                      <p>
                        {robot.state}
                        <br />
                        Position {robot.pos.join(", ")}
                        <br />
                        Battery {fmt(robot.battery)}%<br />
                        Order {robot.task || "none"}
                      </p>
                    </>
                  )}
                </section>
              </div>
              <section className="panel">
                <div className="panel-head">
                  <h2>Event ledger</h2>
                  <select
                    aria-label="Event filter"
                    value={filter}
                    onChange={(e) => setFilter(e.target.value)}
                  >
                    {[
                      "all",
                      "incident",
                      "deadlock",
                      "decision",
                      "order",
                      "command",
                    ].map((f) => (
                      <option key={f}>{f}</option>
                    ))}
                  </select>
                </div>
                <div className="event-ledger">
                  {events
                    .filter((e) => filter === "all" || e.kind === filter)
                    .slice(-150)
                    .reverse()
                    .map((e) => (
                      <details key={e.seq}>
                        <summary>
                          <button
                            className="text-button"
                            onClick={() => setHistoryTick(e.tick)}
                          >
                            T+{e.tick}
                          </button>
                          <span className="badge">{e.kind}</span>
                          {e.message}
                        </summary>
                        {e.candidates ? (
                          <table>
                            <thead>
                              <tr>
                                <th>Robot</th>
                                <th>Score</th>
                                <th>Distance</th>
                                <th>Congestion</th>
                                <th>Eligible</th>
                              </tr>
                            </thead>
                            <tbody>
                              {e.candidates.map((c) => (
                                <tr key={c.robot}>
                                  <td>{c.robot}</td>
                                  <td>{fmt(c.score)}</td>
                                  <td>{c.distance}</td>
                                  <td>{c.congestion}</td>
                                  <td>
                                    {c.available && c.sufficient ? "Yes" : "No"}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        ) : (
                          <p>
                            Recorded at simulation tick {e.tick}. Select the
                            tick to inspect its snapshot.
                          </p>
                        )}
                      </details>
                    ))}
                </div>
              </section>
            </>
          )}
          {tab === "What-if laboratory" && live && (
            <>
              <section className="panel lab-config">
                <div>
                  <h2>A controlled comparison</h2>
                  <p>
                    Fork run #{runId}&apos;s layout and seed into two fresh
                    scenarios.
                    <br />
                    Both receive the same 60 initial orders and run for 300
                    ticks.
                  </p>
                </div>
                <label>
                  Variant fleet
                  <input
                    type="number"
                    value={expFleet}
                    min={1}
                    max={80}
                    onChange={(e) => setExpFleet(Number(e.target.value))}
                  />
                </label>
                <label>
                  Dispatch policy
                  <select
                    value={policy}
                    onChange={(e) => setPolicy(e.target.value)}
                  >
                    <option value="improved">Improved scoring</option>
                    <option value="baseline">Baseline FIFO</option>
                  </select>
                </label>
                <label>
                  Order priority
                  <input
                    type="number"
                    value={expPriority}
                    min={1}
                    max={5}
                    onChange={(e) => setExpPriority(Number(e.target.value))}
                  />
                </label>
                <label>
                  Extra orders / 30 ticks
                  <input
                    type="number"
                    value={arrival}
                    min={0}
                    max={20}
                    onChange={(e) => setArrival(Number(e.target.value))}
                  />
                </label>
                <label className="inline">
                  <input
                    type="checkbox"
                    checked={removeCharger}
                    onChange={(e) => setRemoveCharger(e.target.checked)}
                  />
                  Remove last charger
                </label>
                <label className="inline">
                  <input
                    type="checkbox"
                    checked={expBlock}
                    onChange={(e) => setExpBlock(e.target.checked)}
                  />
                  Block cell {cell.join(", ")}
                </label>
                <Button
                  disabled={!canOperate || busy || expStatus === "pending"}
                  onClick={() =>
                    void act(async () => {
                      const e = await api<{ id: number }>("/experiments", {
                        run_id: runId,
                        changes: {
                          fleet: expFleet,
                          policy,
                          remove_charger: removeCharger,
                          blocked: expBlock ? cell : null,
                          arrival_rate: arrival,
                          priority: expPriority,
                        },
                        ticks: 300,
                        count: 60,
                      });
                      setExperimentId(e.id);
                      setResult(null);
                      setExpStatus("pending");
                    })
                  }
                >
                  <FlaskConical size={16} />
                  {expStatus === "pending"
                    ? "Computing scenarios…"
                    : "Run experiment"}
                </Button>
              </section>
              {result ? (
                <>
                  <section className="panel">
                    <div className="panel-head">
                      <h2>Completed deliveries / simulated time</h2>
                      <span className="badge">
                        COMPUTED · SEED {result.seed}
                      </span>
                    </div>
                    <div className="chart">
                      <ResponsiveContainer width="100%" height={280}>
                        <LineChart data={result.series}>
                          <CartesianGrid
                            stroke="#26313b"
                            strokeDasharray="3 3"
                          />
                          <XAxis dataKey="tick" stroke="#8998a8" />
                          <YAxis stroke="#8998a8" />
                          <Tooltip
                            contentStyle={{
                              background: "#17212b",
                              border: "1px solid #35424d",
                            }}
                          />
                          <Line
                            type="monotone"
                            dataKey="baseline"
                            name="Baseline"
                            stroke="#91a7d1"
                            dot={false}
                            strokeWidth={2}
                          />
                          <Line
                            type="monotone"
                            dataKey="variant"
                            name="Variant"
                            stroke="#77e7c4"
                            dot={false}
                            strokeWidth={2}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </section>
                  <section className="panel">
                    <div className="panel-head">
                      <h2>Measured comparison</h2>
                      <div className="inline">
                        {["csv", "json"].map((f) => (
                          <a
                            key={f}
                            className="button outline"
                            href={`${API}/api/v1/reports/experiments/${experimentId}?format=${f}`}
                          >
                            Export {f.toUpperCase()} ↗
                          </a>
                        ))}
                      </div>
                    </div>
                    <table>
                      <thead>
                        <tr>
                          <th>METRIC</th>
                          <th>BASELINE</th>
                          <th>VARIANT</th>
                          <th>ABSOLUTE Δ</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.keys(result.baseline).map((k) => (
                          <tr key={k}>
                            <td>{k.replaceAll("_", " ")}</td>
                            <td>{fmt(result.baseline[k])}</td>
                            <td>{fmt(result.variant[k])}</td>
                            <td>
                              {result.delta[k] > 0 ? "+" : ""}
                              {fmt(result.delta[k])}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <p className="panel-note">{result.method}</p>
                  </section>
                </>
              ) : (
                <div className="panel empty lab-empty">
                  <FlaskConical size={34} />
                  <h2>
                    {expStatus === "pending"
                      ? "The worker is running both scenarios."
                      : "Evidence before intuition."}
                  </h2>
                  <p>
                    Results appear only after the simulation completes. No
                    estimated improvements.
                  </p>
                </div>
              )}
            </>
          )}
          {tab === "Administration" && isAdmin && (
            <div className="lower-grid">
              <section className="panel">
                <div className="panel-head">
                  <h2>Workspace access</h2>
                  <Settings size={16} />
                </div>
                <table>
                  <thead>
                    <tr>
                      <th>USER</th>
                      <th>ROLE</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((u) => (
                      <tr key={u.id}>
                        <td>{u.username}</td>
                        <td>{u.role}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <form
                  className="admin-form"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const f = new FormData(e.currentTarget);
                    void act(async () => {
                      await api("/users", {
                        username: f.get("username"),
                        password: f.get("password"),
                        role: f.get("role"),
                      });
                      setUsers(await api("/users"));
                      setNotice("User created.");
                    });
                  }}
                >
                  <h3>Create account</h3>
                  <label>
                    Username
                    <input name="username" required />
                  </label>
                  <label>
                    Password
                    <input
                      name="password"
                      type="password"
                      minLength={12}
                      required
                      autoComplete="new-password"
                    />
                  </label>
                  <label>
                    Role
                    <select name="role">
                      <option>VIEWER</option>
                      <option>OPERATOR</option>
                      <option>ADMIN</option>
                    </select>
                  </label>
                  <Button disabled={busy}>Create user</Button>
                </form>
              </section>
              <section className="panel">
                <div className="panel-head">
                  <h2>Audit log</h2>
                  <Button
                    variant="ghost"
                    onClick={() =>
                      void act(async () => setAudit(await api("/audit")))
                    }
                  >
                    Refresh
                  </Button>
                </div>
                <div className="timeline">
                  {audit.map((a) => (
                    <div key={a.id}>
                      <i className="dot" />
                      <div>
                        {a.action}
                        <small>{new Date(a.created).toLocaleString()}</small>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            </div>
          )}
          <footer className="console-footer">
            <span>
              <Boxes size={13} /> FleetVerse / warehouse intelligence
            </span>
            <span>Deterministic engine · All activity is simulated</span>
          </footer>
        </div>
      </main>
    </div>
  );
}
