import { Plane, Car, RadioTower, LucideIcon } from 'lucide-react';
import { DeploymentInput, DeploymentStatus, DeploymentType, Level } from './api';

// Type → icon + label. Adding a type here + in the backend TYPES is all it takes.
export const TYPE_ICON: Record<DeploymentType, LucideIcon> = {
  drone: Plane,
  rover: Car,
  sensor: RadioTower,
};

export const TYPE_LABEL: Record<DeploymentType, string> = {
  drone: 'Drone',
  rover: 'Rover',
  sensor: 'Sensor',
};

export const STATUS_LEVEL: Record<DeploymentStatus, Level> = {
  online: 'ok',
  degraded: 'warn',
  offline: 'idle',
};

// Protocols shown in the form. Supported ones come from the backend at runtime;
// these extras render disabled to signal what's planned.
export const FUTURE_PROTOCOLS = ['ros2', 'mqtt', 'zenoh'];

export const PROTOCOL_LABEL: Record<string, string> = {
  mavlink: 'MAVLink',
  ros2: 'ROS 2',
  mqtt: 'MQTT',
  zenoh: 'Zenoh',
};

export function blankDeployment(): DeploymentInput {
  return {
    name: '',
    type: 'drone',
    mode: 'simulator',
    protocol: 'mavlink',
    host: '127.0.0.1',
    port: 14550,
    description: '',
    containers: [],
    telemetry: {},
  };
}
