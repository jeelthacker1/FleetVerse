export type Cell = [number, number];
export type Layout = {
  name: string;
  width: number;
  height: number;
  blocked: Cell[];
  restricted: Cell[];
  pickup: Cell[];
  dropoff: Cell[];
  chargers: Cell[];
  checkpoints: Cell[];
  lanes: Record<string, string>;
};
export type Robot = {
  id: string;
  pos: Cell;
  destination: Cell | null;
  route: Cell[];
  battery: number;
  state: string;
  task: string | null;
  load: number;
  capacity: number;
  speed: number;
  distance: number;
  completed: number;
  failures: number[];
  wait: number;
  idle: number;
  busy: number;
};
export type Order = {
  id: string;
  pickup: Cell;
  dropoff: Cell;
  priority: number;
  status: string;
  robot: string | null;
  created: number;
  started: number | null;
  finished: number | null;
  deadline: number;
  eta: number | null;
  history: { tick: number; status: string }[];
};
export type SimEvent = {
  seq: number;
  tick: number;
  kind: string;
  message: string;
  candidates?: {
    robot: string;
    score: number;
    available: boolean;
    sufficient: boolean;
    distance: number;
    congestion: number;
    battery: number;
  }[];
};
export type State = {
  tick: number;
  status: string;
  speed: number;
  seed: number;
  policy: string;
  layout: Layout;
  robots: Robot[];
  orders: Order[];
  events: SimEvent[];
  blocked: Cell[];
  failed_chargers: Cell[];
  unavailable: Cell[];
  planning: Record<string, number>;
};
export type Payload = {
  id: number;
  revision: number;
  state: State;
  metrics: Record<string, number>;
  historical?: boolean;
};
export type User = { username: string; role: string; csrf: string };
export type LayoutRecord = {
  id: number;
  name: string;
  warehouse_id: number;
  data: Layout;
};
export type ExperimentResult = {
  baseline: Record<string, number>;
  variant: Record<string, number>;
  delta: Record<string, number>;
  series: { tick: number; baseline: number; variant: number }[];
  method: string;
  seed: number;
  ticks: number;
  workload: number;
};
