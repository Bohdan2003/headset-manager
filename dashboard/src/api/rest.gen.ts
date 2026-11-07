/* Сгенерировано из server/schema/rest.json (npm run gen:types). Не править руками. */

export type Rest = AuthStatus | CommandCreate | CommandView[] | Stats | SetupInfo | SetupRequest | WifiUpdateRequest;
export type Configured = boolean;
export type Authenticated = boolean;
export type Cansetup = boolean;
/**
 * @minItems 1
 * @maxItems 200
 */
export type Headsetids = [string, ...string[]];
export type Cmd =
  | "launch"
  | "show_menu"
  | "set_sleep"
  | "guard"
  | "close_game"
  | "restart_game"
  | "reboot"
  | "sleep"
  | "power_off"
  | "request_access"
  | "update_agent";
export type Ttls = number;
export type Id = string;
export type Headsetid = string;
export type Cmd1 =
  | "launch"
  | "show_menu"
  | "set_sleep"
  | "guard"
  | "close_game"
  | "restart_game"
  | "reboot"
  | "sleep"
  | "power_off"
  | "request_access"
  | "update_agent";
export type Status = "sent" | "acked" | "failed" | "timeout";
export type Reason =
  ("offline" | "asleep" | "timeout" | "no_adb" | "not_allowed" | "failed" | "expired" | "bad_params") | null;
export type Detail = string | null;
export type Createdat = string;
export type Ackedat = string | null;
export type Period = "today" | "7d" | "30d";
export type From = string;
export type To = string;
export type Plays = number;
export type Sessions = number;
export type Exits = number;
export type Guardreturns = number;
export type Package = string;
export type Title = string;
export type Plays1 = number;
export type Sessions1 = number;
export type Avgsessions = number;
export type Exits1 = number;
export type Guardreturns1 = number;
export type Endedbyplayer = number;
export type Endedbyoperator = number;
export type Games = StatsGame[];
export type Headsetid1 = string;
export type Label = string;
export type Plays2 = number;
export type Sessions2 = number;
export type Disconnects = number;
export type Chargeinterruptions = number;
export type Batterydrainperhour = number | null;
export type Batterylifeh = number | null;
export type Headsets = StatsHeadset[];
export type Date = string;
export type Plays3 = number;
export type Days = StatsDay[];
export type Bundledversion = string;
export type Adbid = string;
export type Transport = "usb" | "wifi";
export type State = string;
export type Status1 = string;
export type Bundledversion1 = string;
export type Serial = string | null;
export type Model = string | null;
export type Installedversion = string | null;
export type Permissionsok = boolean | null;
export type Headsetid2 = string | null;
export type Label1 = string | null;
export type Devices = SetupDevice[];
export type Headsetid3 = string;
export type Label2 = string;
export type Online = boolean;
export type Agentversion = string | null;
export type Adb =
  ("ready" | "no_wifi" | "waiting_confirmation" | "connecting" | "key_missing" | "key_rejected" | "error") | null;
export type Status2 = string;
export type Fleet = FleetHeadset[];
export type Id1 = string;
export type Kind = "install" | "update" | "remove";
export type Adbid1 = string;
export type Status3 = "running" | "waiting_user" | "done" | "failed";
export type Log = string[];
export type Error = string | null;
export type Kind1 = "install" | "update" | "remove";
export type Adbid2 = string;
export type Label3 = string | null;
/**
 * @minItems 1
 * @maxItems 200
 */
export type Headsetids1 = [string, ...string[]];

export interface AuthStatus {
  configured: Configured;
  authenticated: Authenticated;
  canSetup: Cansetup;
}
/**
 * Запрос дашборда: одна команда нескольким шлемам.
 */
export interface CommandCreate {
  headsetIds: Headsetids;
  cmd: Cmd;
  params: Params;
  ttlS: Ttls;
}
export interface Params {
  [k: string]: unknown;
}
/**
 * Команда одному шлему и её судьба.
 */
export interface CommandView {
  id: Id;
  headsetId: Headsetid;
  cmd: Cmd1;
  params: Params1;
  status: Status;
  reason: Reason;
  detail: Detail;
  createdAt: Createdat;
  ackedAt: Ackedat;
}
export interface Params1 {
  [k: string]: unknown;
}
export interface Stats {
  period: Period;
  from: From;
  to: To;
  totals: StatsTotals;
  games: Games;
  headsets: Headsets;
  days: Days;
}
export interface StatsTotals {
  playS: Plays;
  sessions: Sessions;
  exits: Exits;
  guardReturns: Guardreturns;
}
export interface StatsGame {
  package: Package;
  title: Title;
  playS: Plays1;
  sessions: Sessions1;
  avgSessionS: Avgsessions;
  exits: Exits1;
  guardReturns: Guardreturns1;
  endedByPlayer: Endedbyplayer;
  endedByOperator: Endedbyoperator;
}
export interface StatsHeadset {
  headsetId: Headsetid1;
  label: Label;
  playS: Plays2;
  sessions: Sessions2;
  disconnects: Disconnects;
  chargeInterruptions: Chargeinterruptions;
  batteryDrainPerHour: Batterydrainperhour;
  batteryLifeH: Batterylifeh;
}
export interface StatsDay {
  date: Date;
  playS: Plays3;
}
export interface SetupInfo {
  bundledVersion: Bundledversion;
  devices: Devices;
  fleet: Fleet;
  job: SetupJob | null;
}
export interface SetupDevice {
  adbId: Adbid;
  transport: Transport;
  state: State;
  status: Status1;
  bundledVersion: Bundledversion1;
  serial: Serial;
  model: Model;
  installedVersion: Installedversion;
  permissionsOk: Permissionsok;
  headsetId: Headsetid2;
  label: Label1;
}
/**
 * Шлем в базе: можно ли обновить его по Wi-Fi.
 */
export interface FleetHeadset {
  headsetId: Headsetid3;
  label: Label2;
  online: Online;
  agentVersion: Agentversion;
  adb: Adb;
  status: Status2;
}
export interface SetupJob {
  id: Id1;
  kind: Kind;
  adbId: Adbid1;
  status: Status3;
  log: Log;
  error: Error;
}
export interface SetupRequest {
  kind: Kind1;
  adbId: Adbid2;
  label: Label3;
}
export interface WifiUpdateRequest {
  headsetIds: Headsetids1;
}
