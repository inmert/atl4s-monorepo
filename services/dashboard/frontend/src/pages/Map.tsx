import { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useTopic } from '../lib/topics';

const TRAIL_MAX_POINTS = 1000;

export function Map() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markerRef = useRef<L.CircleMarker | null>(null);
  const trailRef = useRef<L.Polyline | null>(null);
  const trailPoints = useRef<[number, number][]>([]);
  const centered = useRef(false);

  useEffect(() => {
    if (!containerRef.current) return;
    const map = L.map(containerRef.current).setView([0, 0], 2);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors',
      maxZoom: 19,
    }).addTo(map);
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
      markerRef.current = null;
      trailRef.current = null;
      trailPoints.current = [];
      centered.current = false;
    };
  }, []);

  const gps = useTopic('/mavros/global_position/global');
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !gps?.data) return;
    const { latitude, longitude } = gps.data;
    if (typeof latitude !== 'number' || typeof longitude !== 'number') return;
    if (Math.abs(latitude) < 1e-4 && Math.abs(longitude) < 1e-4) return;

    const pt: [number, number] = [latitude, longitude];
    trailPoints.current.push(pt);
    if (trailPoints.current.length > TRAIL_MAX_POINTS) {
      trailPoints.current.shift();
    }

    if (!markerRef.current) {
      markerRef.current = L.circleMarker(pt, {
        radius: 7,
        color: '#5da9e8',
        fillColor: '#5da9e8',
        fillOpacity: 0.85,
        weight: 2,
      }).addTo(map);
    } else {
      markerRef.current.setLatLng(pt);
    }

    if (!trailRef.current) {
      trailRef.current = L.polyline(trailPoints.current, {
        color: '#5da9e8',
        weight: 2,
        opacity: 0.6,
      }).addTo(map);
    } else {
      trailRef.current.setLatLngs(trailPoints.current);
    }

    if (!centered.current) {
      map.setView(pt, 18);
      centered.current = true;
    }
  }, [gps]);

  const hasFix =
    gps?.data && Math.abs(gps.data.latitude ?? 0) > 1e-4 && Math.abs(gps.data.longitude ?? 0) > 1e-4;

  return (
    <section>
      <div className="page-header">
        <h1>Map</h1>
        <span className="hint">
          {hasFix
            ? `${gps!.data.latitude.toFixed(6)}, ${gps!.data.longitude.toFixed(6)}`
            : 'no GPS fix yet'}
        </span>
      </div>
      <div className="map" ref={containerRef} />
    </section>
  );
}
