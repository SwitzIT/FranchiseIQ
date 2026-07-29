import React, { useEffect } from 'react';
import { Polygon, Tooltip } from 'react-leaflet';
import useAppStore from '../store/useAppStore';
import { getHexHeatmap } from '../services/api';

/**
 * HexHeatmapLayer (v3.3)
 * ──────────────────────
 * Self-contained hex render. Click any hex → opens the detail panel
 * (rendered separately via <HexDetailPanel />). The hover tooltip now
 * shows the dominant locality so users can orient themselves before
 * clicking through.
 *
 * Drop-in usage (no parent wiring needed):
 *     import HexHeatmapLayer from './HexHeatmapLayer';
 *     import HexDetailPanel from './HexDetailPanel';
 *     // inside <MapContainer>:  <HexHeatmapLayer />
 *     // anywhere in your dashboard root: <HexDetailPanel />
 */
export default function HexHeatmapLayer() {
  const {
    sessionId, results, mapLayers,
    hexHeatmap, setHexHeatmap, hexResolutionOverride,
    setSelectedHex,
  } = useAppStore();

  useEffect(() => {
    if (!sessionId || !results) return;
    let cancelled = false;
    console.log('[HexLayer] fetching hex-heatmap…');

    getHexHeatmap(sessionId, hexResolutionOverride)
      .then((data) => {
        if (cancelled) return;
        console.log('[HexLayer] received', data?.hexes?.length, 'cells at res', data?.resolution);
        setHexHeatmap(data);
      })
      .catch((e) => {
        if (cancelled) return;
        console.error('[HexLayer] fetch failed:', e);
      });

    return () => { cancelled = true; };
  }, [sessionId, results, hexResolutionOverride, setHexHeatmap]);

  if (!mapLayers.hexHeatmap) return null;
  if (!hexHeatmap?.hexes?.length) return null;

  return (
    <>
      {hexHeatmap.hexes.map((hex) => {
        const cls = hex.classification;
        const color =
          cls === 'above' ? '#22C55E' :
          cls === 'below' ? '#EF4444' :
          '#F59E0B';

        if (!Array.isArray(hex.boundary) || hex.boundary.length < 3) return null;

        return (
          <Polygon
            key={hex.cell}
            positions={hex.boundary}
            pathOptions={{
              color, fillColor: color,
              fillOpacity: 0.32, weight: 1.5, opacity: 0.9,
            }}
            eventHandlers={{
              click: () => setSelectedHex(hex),
            }}
          >
            <Tooltip direction="top" sticky>
              <div className="text-xs leading-tight">
                {hex.dominant_locality && (
                  <div className="font-bold text-[11px]" style={{ color }}>
                    {hex.dominant_locality}
                  </div>
                )}
                <div className="font-semibold">
                  {hex.store_count} store{hex.store_count !== 1 ? 's' : ''}
                  {' · '}
                  {cls === 'above' ? '↑ above' : cls === 'below' ? '↓ below' : '= on target'}
                  {' · '}
                  {hex.pct_of_network_avg?.toFixed(0)}%
                </div>
                <div className="text-[10px] text-gray-600 mt-0.5">
                  click for details →
                </div>
              </div>
            </Tooltip>
          </Polygon>
        );
      })}
    </>
  );
}
