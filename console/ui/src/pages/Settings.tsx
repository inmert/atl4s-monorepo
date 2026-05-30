import { Settings as SettingsIcon } from 'lucide-react';
import { PagePlaceholder } from '../components/PagePlaceholder';

export function Settings() {
  return (
    <PagePlaceholder
      icon={SettingsIcon}
      title="Settings"
      description="Console preferences and connection settings."
    />
  );
}
