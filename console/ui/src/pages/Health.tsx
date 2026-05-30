import { Activity } from 'lucide-react';
import { PagePlaceholder } from '../components/PagePlaceholder';

export function Health() {
  return (
    <PagePlaceholder
      icon={Activity}
      title="Health"
      description="Container and topic liveness across the pipeline."
    />
  );
}
