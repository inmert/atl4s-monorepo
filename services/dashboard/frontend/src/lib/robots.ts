// Robot helpers shared by Robots / RobotDetail / Home.

import {
  Bot,
  Car,
  MonitorPlay,
  Plane,
  type LucideIcon,
} from 'lucide-react';
import type { Robot } from './api';
import type { TopicMsg } from './topics';

const ICONS: Record<string, LucideIcon> = {
  simulator: MonitorPlay,
  drone: Plane,
  rover: Car,
  bot: Bot,
};

export function iconFor(hint: string): LucideIcon {
  return ICONS[hint] || Bot;
}

const FRESH_SEC = 5;

export function isFresh(topic: TopicMsg | undefined, withinSec = FRESH_SEC): boolean {
  if (!topic) return false;
  return Date.now() / 1000 - topic.ts < withinSec;
}

/** A robot is Online when its `state` topic is fresh and connected:true.
 * Robots without a `state` topic fall back to "any telemetry topic is fresh". */
export function isOnline(
  robot: Robot,
  topics: Record<string, TopicMsg>,
): boolean {
  const stateTopic = robot.telemetry.state;
  if (stateTopic) {
    const t = topics[stateTopic];
    return isFresh(t) && Boolean(t?.data?.connected);
  }
  return Object.values(robot.telemetry).some((tp) => tp && isFresh(topics[tp]));
}

export function summarize(robot: Robot, topics: Record<string, TopicMsg>): string {
  const stateTopic = robot.telemetry.state;
  if (!stateTopic) return 'no state topic';
  const t = topics[stateTopic];
  if (!isFresh(t)) return 'no link';
  const mode = t?.data?.mode || '—';
  const armed = t?.data?.armed ? 'ARMED' : 'disarmed';
  return `${mode} · ${armed}`;
}
