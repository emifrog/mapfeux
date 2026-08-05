import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

/**
 * Garde-fou sur la syntaxe des variables CSS dans les classes utilitaires.
 *
 * Référence : cahier §6.5.
 *
 * Tailwind v3 acceptait `text-[--text-2]` pour dire `color: var(--text-2)`.
 * La v4 a déplacé cette écriture vers les parenthèses, `text-(--text-2)`, et
 * ne reconnaît plus l'ancienne comme une référence de variable : elle la traite
 * en valeur arbitraire littérale et produit `color: --text-2`, qui n'est pas
 * du CSS valide. Le navigateur écarte la déclaration.
 *
 * Le passage en v4 avait conservé l'écriture v3 dans 86 classes. Rien ne le
 * signalait : le lint passe, le typage passe, la construction passe, les pages
 * se rendent. Seules les couleurs et les tailles n'étaient pas celles qu'on
 * croyait — l'échelle typographique de la refonte, notamment, ne s'appliquait
 * nulle part.
 *
 * Un défaut qu'aucune porte de qualité ne voit et qui ne se manifeste qu'à
 * l'œil mérite une porte à lui.
 */

const SOURCE = join(import.meta.dirname, '.');

/** `-[--x]` ou `-[type:--x]` : la référence de variable à l'ancienne. */
const V3_VARIABLE_CLASS = /-\[(?:[a-z]+:)?--[a-z0-9-]+\]/g;

function sourceFiles(directory: string): string[] {
  const found: string[] = [];
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) {
      found.push(...sourceFiles(path));
    } else if (/\.tsx?$/.test(entry.name) && !entry.name.endsWith('.test.ts')) {
      found.push(path);
    }
  }
  return found;
}

describe('variables CSS dans les classes utilitaires', () => {
  it('emploie la syntaxe v4 à parenthèses, jamais celle de la v3', () => {
    const offenders: string[] = [];

    for (const file of sourceFiles(SOURCE)) {
      const matches = readFileSync(file, 'utf8').match(V3_VARIABLE_CLASS);
      if (matches) {
        offenders.push(`${file} : ${[...new Set(matches)].join(', ')}`);
      }
    }

    expect(
      offenders,
      'Écrire text-(--text-2) et non text-[--text-2] : la seconde forme compile ' +
        'en « color: --text-2 », que le navigateur écarte en silence.',
    ).toEqual([]);
  });

  it('reconnaît la forme fautive, y compris avec indication de type', () => {
    // Sans ce contrôle, une expression trop étroite laisserait le test passer
    // sur un dépôt entièrement fautif.
    //
    // Les exemples sont assemblés morceau par morceau, et c'est nécessaire :
    // Tailwind parcourt les sources en texte brut, fichiers de test compris.
    // Écrits d'un seul tenant, ils lui feraient engendrer les deux règles
    // invalides que ce test existe pour interdire — la première version de ce
    // fichier les a effectivement remises dans la feuille de style.
    const brackets = (inner: string) => `text-${'['}${inner}${']'}`;
    expect(brackets('--text-2').match(V3_VARIABLE_CLASS)).not.toBeNull();
    expect(brackets('length:--text-title').match(V3_VARIABLE_CLASS)).not.toBeNull();
  });

  it('laisse passer les vraies valeurs arbitraires', () => {
    // `border-l-[3px]` et consorts ne référencent aucune variable : les
    // signaler ferait abandonner le contrôle.
    expect('border-l-[3px]'.match(V3_VARIABLE_CLASS)).toBeNull();
    expect('h-[calc(100%-2rem)]'.match(V3_VARIABLE_CLASS)).toBeNull();
    expect('text-(--text-2)'.match(V3_VARIABLE_CLASS)).toBeNull();
  });
});
