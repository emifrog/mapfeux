import type { Metadata } from 'next';

import { Prose, Section, ToComplete } from '@/components/prose';

/**
 * Déclaration d'accessibilité. Cahier §6.5 et §28.1.
 *
 * Aucune conformité n'est déclarée : elle exige un audit qui n'a pas eu lieu.
 * Annoncer un niveau non audité serait une déclaration fausse, et priverait
 * les personnes concernées d'une information exacte sur ce qui fonctionne.
 */

export const metadata: Metadata = {
  title: 'Accessibilité',
  description: 'État d’accessibilité du service MapFeux, dispositions prises et limites connues.',
};

export default function AccessibilityPage() {
  return (
    <Prose
      title="Accessibilité"
      lead="Ce qui a été fait, ce qui n’a pas encore été audité, et où le service reste inaccessible."
    >
      <ToComplete>
        <strong>Aucune conformité n’est déclarée à ce jour.</strong> Le service n’a pas fait l’objet
        d’un audit RGAA. Annoncer un niveau de conformité sans audit serait une déclaration
        inexacte. Cette page sera remplacée par une déclaration en bonne et due forme après l’audit.
      </ToComplete>

      <Section title="Dispositions déjà prises">
        <p>
          Les pages principales sont rendues côté serveur et restent entièrement lisibles sans
          JavaScript. La fiche d’un événement, en particulier, affiche l’intégralité de son contenu
          — statuts, horodatages, chronologie, détections — sans exécuter le moindre script.
        </p>
        <p>
          La carte n’est jamais le seul chemin vers l’information : une liste textuelle des
          événements accompagne chaque vue cartographique, et la recherche de commune fonctionne
          entièrement au clavier.
        </p>
        <p>
          Aucune information n’est portée par la couleur seule. Les statuts, les provenances et la
          légende associent systématiquement une couleur et un libellé.
        </p>
        <p>
          Le réglage système de réduction des animations est respecté, et le thème sombre suit la
          préférence du système.
        </p>
      </Section>

      <Section title="Limites connues">
        <p>
          La carte interactive repose sur un canevas WebGL, qui reste inaccessible aux lecteurs
          d’écran. C’est une limite du procédé, pas un oubli : la liste textuelle existe pour cette
          raison et porte la même information.
        </p>
        <p>
          Les contrastes n’ont pas été mesurés systématiquement, et la navigation au clavier n’a pas
          été vérifiée sur l’ensemble des parcours.
        </p>
      </Section>

      <Section title="Signaler un obstacle">
        <ToComplete>
          <strong>À compléter avant toute publication.</strong> Adresse de contact permettant de
          signaler une difficulté d’accès, et voies de recours.
        </ToComplete>
      </Section>
    </Prose>
  );
}
