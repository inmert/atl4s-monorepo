export function Home() {
  return (
    <section>
      <h1>ATL4S</h1>
      <p>Modular drone telemetry and sensor pipeline.</p>
      <ul>
        <li><strong>Live</strong> — telemetry, raw data, camera</li>
        <li><strong>Bags</strong> — browse / upload / delete recordings in GCS</li>
        <li><strong>Record</strong> — start / stop a recording</li>
        <li><strong>Replay</strong> — play a bag onto the DDS bus</li>
        <li><strong>Pipelines</strong> — run a bag through the perception stack</li>
        <li><strong>Health</strong> — pipeline-wide health from <code>/atl4s/health</code></li>
      </ul>
    </section>
  );
}
