import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { jsonSocket } from './ws';

export type TopicMsg = {
  topic: string;
  data: any;
  rate: number;
  ts: number;
};

type TopicMap = Record<string, TopicMsg>;

type TopicContextValue = {
  topics: TopicMap;
  status: 'open' | 'closed';
};

const Ctx = createContext<TopicContextValue>({ topics: {}, status: 'closed' });

// Single shared /ws/topics subscription. Pages and the nav badge consume it
// via useTopics() / useTopic() rather than opening their own sockets.
export function TopicProvider({ children }: { children: ReactNode }) {
  const [topics, setTopics] = useState<TopicMap>({});
  const [status, setStatus] = useState<'open' | 'closed'>('closed');

  useEffect(() => {
    const ws = jsonSocket<TopicMsg>(
      '/ws/topics',
      (msg) => setTopics((s) => ({ ...s, [msg.topic]: msg })),
      setStatus,
    );
    return () => ws.close();
  }, []);

  const value = useMemo(() => ({ topics, status }), [topics, status]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useTopics() {
  return useContext(Ctx);
}

export function useTopic(name: string): TopicMsg | undefined {
  return useContext(Ctx).topics[name];
}
