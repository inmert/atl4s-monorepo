import { LayoutDashboard } from 'lucide-react';
import { PagePlaceholder } from '../components/PagePlaceholder';

export function Dashboard() {
  return (
    <PagePlaceholder
      icon={LayoutDashboard}
      title="Dashboard"
      description="Fleet overview — telemetry, pipelines, and active tasks at a glance."
    />
  );
}
