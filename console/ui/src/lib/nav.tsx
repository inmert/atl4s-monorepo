import { ReactElement } from 'react';
import { Activity, Box, Database, LayoutDashboard, Rocket, Settings as SettingsIcon, Workflow, LucideIcon } from 'lucide-react';
import { Dashboard } from '../pages/Dashboard';
import { Containers } from '../pages/Containers';
import { Deployments } from '../pages/Deployments';
import { Pipelines } from '../pages/Pipelines';
import { RosbagManager } from '../pages/RosbagManager';
import { Health } from '../pages/Health';
import { Settings } from '../pages/Settings';

// Single source of truth for navigation + routing. The Sidebar renders these as
// links; App turns them into routes. `path: ''` is the index route ("/").
export interface NavItem {
  path: string;
  label: string;
  icon: LucideIcon;
  element: ReactElement;
}

export const PRIMARY_NAV: NavItem[] = [
  { path: '', label: 'Dashboard', icon: LayoutDashboard, element: <Dashboard /> },
  { path: 'containers', label: 'Containers', icon: Box, element: <Containers /> },
  { path: 'deployments', label: 'Deployments', icon: Rocket, element: <Deployments /> },
  { path: 'pipelines', label: 'Pipelines', icon: Workflow, element: <Pipelines /> },
  { path: 'rosbags', label: 'Rosbag Manager', icon: Database, element: <RosbagManager /> },
  { path: 'health', label: 'Health', icon: Activity, element: <Health /> },
];

// Pinned to the bottom of the sidebar.
export const SETTINGS_NAV: NavItem = {
  path: 'settings',
  label: 'Settings',
  icon: SettingsIcon,
  element: <Settings />,
};

export const ALL_NAV: NavItem[] = [...PRIMARY_NAV, SETTINGS_NAV];

export const navHref = (path: string): string => (path === '' ? '/' : `/${path}`);
