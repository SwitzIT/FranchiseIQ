import React, { useEffect } from 'react';
import { Polygon, Tooltip } from 'react-leaflet';
import useAppStore from '../store/useAppStore';
import { getCompetitorDensityHexes } from '../services/api';

/**
 * CompetitorDensityLayer (v3.1 drop-in)
 * ─────────────────────────────────────
 * Renders competitor store density as red-tinted hexes. Self-contained:
 * fetches its own data, respects the toggle, no parent wiring required.
 *
 *     import CompetitorDensityLayer from './CompetitorDensityLayer';
 *     // inside <MapContainer>:
 *     <CompetitorDensityLayer />
 */
export default function CompetitorDensityLayer() {
  const {
    sessionId, competitors, mapLayers,
    competitorDensityHexes, setCompetitorDensityHexes,
  } = useAppStore();

  useEffect(() => {
    if (!sessionId || !competitors || competitors.length === 0) return;
    let cancelled = false;

    console.log('[CompetitorDensity] fetching density hexes…');
    getCompetitorDensityHexes(sessionId, 6)
      .then((data) => {
        if (cancelled) return;
        console.log('[CompetitorDensity] received', data?.hexes?.length, 'cells');
        setCompetitorDensityHexes(data);
      })
      .catch((e) => {
        if (cancelled) return;
        console.warn('[CompetitorDensity] fetch failed:', e);
      });

    return () => { cancelled = true; };
  }, [sessionId, competitors, setCompetitorDensityHexes]);

  if (!mapLayers.competitorDensity || !competitorDensityHexes?.hexes?.length) {
    return null;
  }

  const maxCount = Math.max(
    1, ...competitorDensityHexes.hexes.map((h) => h.competitor_count)
  );

  return (
    <>
      {competitorDensityHexes.hexes.map((hex) => {
        const intensity = hex.competitor_count / maxCount;
        if (!Array.isArray(hex.boundary) || hex.boundary.length < 3) return null;

        return (
          <Polygon
            key={`comp-${hex.cell}`}
            positions={hex.boundary}
            pathOptions={{
              color: '#DC2626',
              fillColor: '#DC2626',
              fillOpacity: 0.15 + intensity * 0.45,
              weight: 1,
            }}
          >
            <Tooltip direction="top" sticky>
              <div className="text-xs leading-tight">
                <div className="font-bold mb-0.5">
                  {hex.competitor_count} competitor store{hex.competitor_count !== 1 ? 's' : ''}
                </div>
                {hex.brands && Object.keys(hex.brands).length > 0 && (
                  <div className="text-[10px] text-gray-600 mt-0.5 max-w-[200px]">
                    {Object.entries(hex.brands).slice(0, 4).map(([b, n]) =>
                      <div key={b}>{b}: {n}</div>
                    )}
                  </div>
                )}
              </div>
            </Tooltip>
          </Polygon>
        );
      })}
    </>
  );
}
