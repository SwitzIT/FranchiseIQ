import useAppStore from '../store/useAppStore';
import { loadPreloaded, fetchAmenities, runPrediction, getRegionKpis } from './api';

export const DEFAULT_TOP_N = 10;

/**
 * Runs the full analysis for an already-selected country/state session and
 * opens the dashboard: load the preloaded data files, load amenities, run
 * the prediction model, then fetch region KPIs.
 *
 * Used right after login so users with an assigned country land straight on
 * the dashboard instead of the "Verify Datasets / Configure & Run" screen.
 * Throws on failure so the caller can fall back to that screen.
 */
export async function runFullPipeline(sessionId, stateName, topN = DEFAULT_TOP_N) {
  const store = useAppStore.getState();

  store.setLoading(true, `Loading data for ${stateName}…`);
  const stats = await loadPreloaded(sessionId);
  store.setDataStats(stats);
  store.setHasBU(stats.has_bu);

  store.setLoading(true, `Loading local amenities for ${stateName}…`);
  const amenRes = await fetchAmenities(sessionId);
  store.setAmenitiesInfo(amenRes);

  store.setLoading(true, `Finding the top ${topN} locations in ${stateName}…`);
  const predRes = await runPrediction(sessionId, topN);
  store.setResults(predRes);

  const regionKpis = await getRegionKpis(sessionId);
  store.setRegionKpis(regionKpis);

  store.setStep('dashboard');
}
