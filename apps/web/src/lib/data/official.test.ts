import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

/**
 * Informations officielles : la panne se dit, le vide se lit. « Aucune
 * publication captée » sur une base muette enverrait le lecteur vérifier chez
 * la préfecture des publications qui sont en base (audit du 15 septembre 2026).
 */

vi.mock('server-only', () => ({}));

const rpc = vi.fn();
vi.mock('@/lib/supabase/server', () => ({
  createPublicReadClient: () => ({ rpc }),
}));

const { fetchDepartmentMassifLevels, fetchDepartmentOfficialItems, fetchEventOfficialItems } =
  await import('./official');

const FAILURE = { data: null, error: { code: '57014', message: 'statement timeout' } };
const NOTHING = { data: [], error: null };

beforeEach(() => {
  vi.spyOn(console, 'error').mockImplementation(() => {});
});

afterEach(() => {
  rpc.mockReset();
  vi.restoreAllMocks();
});

describe('lectures officielles', () => {
  it('publications d’un département : erreur → non lisible ; rien → vide lu', async () => {
    rpc.mockResolvedValueOnce(FAILURE);
    expect(await fetchDepartmentOfficialItems('83')).toEqual({ readable: false });
    rpc.mockResolvedValueOnce(NOTHING);
    expect(await fetchDepartmentOfficialItems('83')).toEqual({ readable: true, value: [] });
  });

  it('niveaux des massifs : erreur → non lisible', async () => {
    rpc.mockResolvedValueOnce(FAILURE);
    expect(await fetchDepartmentMassifLevels('83')).toEqual({ readable: false });
  });

  it('publications rapprochées d’un événement : erreur → non lisible', async () => {
    rpc.mockResolvedValueOnce(FAILURE);
    expect(await fetchEventOfficialItems('MPF-AAAAAAAA')).toEqual({ readable: false });
  });
});
