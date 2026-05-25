// Showcase page for the lib/ui primitives. Not linked from the sidebar —
// reach it via /_ui. Useful as a visual reference while migrating pages
// and to catch regressions after primitive changes.

import { useState } from 'react';
import {
  AlertTriangle,
  Camera,
  Check,
  Pause,
  Play,
  Plus,
  Save,
  Trash2,
} from 'lucide-react';

import {
  Badge,
  Button,
  Card,
  Drawer,
  EmptyState,
  IconButton,
  KeyValue,
  Modal,
  PageHeader,
  Pill,
  Spinner,
  StatTile,
  StatusDot,
  Subnav,
  Toggle,
} from '../lib/ui';

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card title={title}>
      <div className="ui-row">{children}</div>
    </Card>
  );
}

export function UIShowcase() {
  const [modalOpen, setModalOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [toggleA, setToggleA] = useState(false);
  const [toggleB, setToggleB] = useState(true);
  const [subnav, setSubnav] = useState('overview');

  return (
    <>
      <PageHeader
        title="UI showcase"
        subtitle={
          <>
            Reference for primitives in <code>lib/ui</code>. Not linked from the
            sidebar — reach it via <code>/_ui</code>.
          </>
        }
      />

      <div className="stack">
        <Section title="Button — variants × sizes">
          <Button>Primary</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="danger" iconLeft={Trash2}>
            Danger
          </Button>
          <Button variant="link">Link</Button>
          <Button iconLeft={Save}>Save</Button>
          <Button iconRight={Plus} size="sm">
            Add small
          </Button>
          <Button loading>Saving…</Button>
          <Button disabled>Disabled</Button>
        </Section>

        <Section title="IconButton">
          <IconButton icon={Play} label="Start" variant="primary" />
          <IconButton icon={Pause} label="Pause" />
          <IconButton icon={Trash2} label="Delete" variant="danger" />
          <IconButton icon={Camera} label="Snapshot" size="sm" />
        </Section>

        <Section title="Pill">
          <Pill>Default</Pill>
          <Pill tone="accent" dot>
            Accent
          </Pill>
          <Pill tone="ok" icon={Check}>
            Healthy
          </Pill>
          <Pill tone="warn" icon={AlertTriangle}>
            3 warnings
          </Pill>
          <Pill tone="err" dot>
            Failed
          </Pill>
        </Section>

        <Section title="Badge + StatusDot">
          <Badge>neutral</Badge>
          <Badge tone="ok">running</Badge>
          <Badge tone="idle">idle</Badge>
          <Badge tone="warn">stale</Badge>
          <Badge tone="err">err</Badge>
          <Badge tone="accent">new</Badge>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <StatusDot tone="ok" /> Gazebo Drone
          </span>
        </Section>

        <Section title="Toggle">
          <Toggle checked={toggleA} onChange={setToggleA} label="Enable tracking" />
          <Toggle checked={toggleB} onChange={setToggleB} label="On example" />
          <Toggle checked={false} onChange={() => {}} disabled label="Disabled" />
        </Section>

        <Section title="Spinner">
          <Spinner />
          <Spinner size={20} />
          <Spinner size={28} />
        </Section>

        <Card title="StatTile (block-level stats for page headers)">
          <div className="stat-grid">
            <StatTile label="Battery" value="100%" tone="ok" />
            <StatTile label="Voltage" value="12.60 V" />
            <StatTile label="Mode" value="STABILIZE" />
            <StatTile label="Pipelines running" value="1 / 1" tone="ok" />
          </div>
        </Card>

        <Card title="KeyValue (dense label/value lists)">
          <KeyValue label="Container" value="atl4s-perception-lidar" mono />
          <KeyValue label="Input topic" value="/lidar/points" mono />
          <KeyValue label="Output rate" value="5.0 Hz" />
          <KeyValue label="Last detection" value="2 s ago" />
        </Card>

        <Section title="Subnav">
          <Subnav
            items={[
              { id: 'overview', label: 'Overview' },
              { id: 'topics', label: 'Topics' },
              { id: 'config', label: 'Config' },
            ]}
            active={subnav}
            onSelect={setSubnav}
          />
        </Section>

        <Section title="Modal + Drawer">
          <Button onClick={() => setModalOpen(true)} iconLeft={Plus}>
            Open modal
          </Button>
          <Button variant="ghost" onClick={() => setDrawerOpen(true)}>
            Open drawer
          </Button>
        </Section>

        <Card title="EmptyState">
          <EmptyState icon={Camera} title="No frames yet">
            Start a camera stream to see live frames here.
          </EmptyState>
        </Card>
      </div>

      {modalOpen && (
        <Modal title="New recording" onClose={() => setModalOpen(false)}>
          <p>Modal content. Press Escape or click the backdrop to dismiss.</p>
          <div className="form-actions">
            <Button variant="ghost" onClick={() => setModalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => setModalOpen(false)} iconLeft={Save}>
              Save
            </Button>
          </div>
        </Modal>
      )}

      <Drawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title="Configure perception-lidar"
      >
        <p>Drawer content. Press Escape or click outside to dismiss.</p>
        <KeyValue label="Model" value="pointpillars" mono />
        <KeyValue label="Confidence" value="0.5" />
        <div className="form-actions">
          <Button variant="ghost" onClick={() => setDrawerOpen(false)}>
            Cancel
          </Button>
          <Button onClick={() => setDrawerOpen(false)}>Apply</Button>
        </div>
      </Drawer>
    </>
  );
}
