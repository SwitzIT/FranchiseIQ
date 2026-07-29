import React, { useEffect } from 'react';
import { Polygon, Tooltip } from 'react-leaflet';
import useAppStore from '../store/useAppStore';
import { getUntappedDemand } from '../services/api';

/**
 * UntappedDemandLayer (v3.1 drop-in)
 * ──────────────────────────────────
 * Renders high-demand × low-supply hexes as blue-tinted polygons.
 *
 *     import UntappedDemandLayer from './UntappedDemandLayer';
 *     // inside <MapContainer>:
 *     <UntappedDemandLayer />
 */
export default function UntappedDemandLayer() {
  const {
    sessionId, results, mapLayers,
    untappedDemand, setUntappedDemand,
    setUntappedDemandLoading,
  } = useAppStore();

  useEffect(() => {
    if (!sessionId || !results) return;
    let cancelled = false;

    console.log('[UntappedDemand] fetching…');
    setUntappedDemandLoading(true);
    getUntappedDemand(sessionId, { resolution: 6, supplyRadiusKm: 3.0 })
      .then((data) => {
        if (cancelled) return;
        console.log('[UntappedDemand] received', data?.hexes?.length, 'cells');
        setUntappedDemand(data);
      })
      .catch((e) => {
        if (cancelled) return;
        console.warn('[UntappedDemand] fetch failed:', e);
      })
      .finally(() => { if (!cancelled) setUntappedDemandLoading(false); });

    return () => { cancelled = true; };
  }, [sessionId, results, setUntappedDemand, setUntappedDemandLoading]);

  if (!mapLayers.untappedDemand || !untappedDemand?.hexes?.length) {
    return null;
  }

  return (
    <>
      {untappedDemand.hexes.map((hex) => {
        const c = hex.classification;
        const fillColor =
          c === 'high' ? '#2563EB' :
          c === 'medium' ? '#3B82F6' :
          '#93C5FD';

        if (!Array.isArray(hex.boundary) || hex.boundary.length < 3) return null;

        return (
          <Polygon
            key={`untapped-${hex.cell}`}
            positions={hex.boundary}
            pathOptions={{
              color: fillColor,
              fillColor,
              fillOpacity: 0.2 + hex.untapped_score * 0.4,
              weight: 1,
            }}
          >
            <Tooltip direction="top" sticky>
              <div className="text-xs leading-tight">
                <div className="font-bold mb-0.5">
                  Untapped score {Math.round(hex.untapped_score * 100)}%
                </div>
                {hex.population > 0 && (
                  <div>Population {hex.population.toLocaleString()}</div>
                )}
                {hex.nearest_store_km != null && (
                  <div className="text-[10px] text-gray-600">
                    Nearest store: {hex.nearest_store_km} km
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
