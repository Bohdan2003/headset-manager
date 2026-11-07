/* Сгенерировано из server/schema/live.json (npm run gen:types). Не править руками. */

export type Live = LiveSnapshot | LiveHeadset | LiveCommand;
export type Type = "snapshot";
export type Id = string;
export type Label = string;
export type Serial = string;
export type Online = boolean;
export type Battery = number | null;
export type Charging = boolean | null;
export type Temp = number | null;
export type Currentpkg = string | null;
export type Adb =
  ("ready" | "no_wifi" | "waiting_confirmation" | "connecting" | "key_missing" | "key_rejected" | "error") | null;
export type Sleepdisabled = boolean | null;
export type Agentversion = string | null;
export type Lastseen = string | null;
export type Guardpkg = string | null;
export type Screenon = boolean | null;
export type Stage = "starting" | "downloading" | "installing" | "failed";
export type Percent = number;
export type Reason = string | null;
export type Side = "left" | "right";
export type Battery1 = number | null;
export type Connected = boolean;
export type Controllers = ControllerInfo[];
export type Package = string;
export type Title = string;
export type Vr = boolean | null;
export type Apps = AppInfo[];
export type Headsets = HeadsetView[];
export type Id1 = string;
export type Headsetid = string;
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
export type Status = "sent" | "acked" | "failed" | "timeout";
export type Reason1 =
  ("offline" | "asleep" | "timeout" | "no_adb" | "not_allowed" | "failed" | "expired" | "bad_params") | null;
export type Detail = string | null;
export type Createdat = string;
export type Ackedat = string | null;
export type Commands = CommandView[];
export type Type1 = "headset";
export type Type2 = "command";

/**
 * Отправляется дашборду сразу после подключения к /live.
 */
export interface LiveSnapshot {
  type: Type;
  headsets: Headsets;
  commands: Commands;
}
/**
 * Шлем, как его видит дашборд.
 */
export interface HeadsetView {
  id: Id;
  label: Label;
  serial: Serial;
  online: Online;
  battery: Battery;
  charging: Charging;
  temp: Temp;
  currentPkg: Currentpkg;
  adb: Adb;
  sleepDisabled: Sleepdisabled;
  agentVersion: Agentversion;
  lastSeen: Lastseen;
  guardPkg: Guardpkg;
  screenOn: Screenon;
  update: UpdateProgress | null;
  controllers: Controllers;
  apps: Apps;
}
/**
 * Как идёт обновление агента по Wi-Fi.
 */
export interface UpdateProgress {
  stage: Stage;
  percent: Percent;
  reason: Reason;
}
export interface ControllerInfo {
  side: Side;
  battery: Battery1;
  connected: Connected;
}
export interface AppInfo {
  package: Package;
  title: Title;
  vr: Vr;
}
/**
 * Команда одному шлему и её судьба.
 */
export interface CommandView {
  id: Id1;
  headsetId: Headsetid;
  cmd: Cmd;
  params: Params;
  status: Status;
  reason: Reason1;
  detail: Detail;
  createdAt: Createdat;
  ackedAt: Ackedat;
}
export interface Params {
  [k: string]: unknown;
}
/**
 * Изменилось состояние одного шлема.
 */
export interface LiveHeadset {
  type: Type1;
  headset: HeadsetView;
}
/**
 * Команда создана или изменился её статус.
 */
export interface LiveCommand {
  type: Type2;
  command: CommandView;
}
