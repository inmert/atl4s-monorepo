import { Database } from 'lucide-react';
import { PagePlaceholder } from '../components/PagePlaceholder';

export function RosbagManager() {
  return (
    <PagePlaceholder
      icon={Database}
      title="Rosbag Manager"
      description="Record, upload, browse, and replay rosbags to and from GCS."
    />
  );
}
