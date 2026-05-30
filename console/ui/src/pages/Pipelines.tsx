import { Workflow } from 'lucide-react';
import { PagePlaceholder } from '../components/PagePlaceholder';

export function Pipelines() {
  return (
    <PagePlaceholder
      icon={Workflow}
      title="Pipelines"
      description="Perception and fusion services — config, lifecycle, and run-on-bag."
    />
  );
}
