import type { Metadata } from 'next';

import { Prose, Section, ToComplete } from '@/components/prose';

/**
 * Mentions légales. Cahier §28.1.
 *
 * Les informations d'identification de l'éditeur ne sont pas inventées. Un nom
 * de directeur de publication, un numéro d'immatriculation ou des coordonnées
 * d'hébergeur plausibles mais faux constitueraient une fausse mention légale —
 * pire que leur absence, puisqu'ils passeraient inaperçus.
 */

export const metadata: Metadata = {
  title: 'Mentions légales',
  description: 'Éditeur, directeur de publication et hébergeur du service MapFeux.',
};

export default function LegalPage() {
  return (
    <Prose eyebrow="légal" title="Mentions légales">
      <Section title="Éditeur">
        <ToComplete>
          <strong>À compléter avant toute publication.</strong> Raison sociale, forme juridique,
          capital, siège social, numéro d’immatriculation et adresse de contact de l’éditeur.
        </ToComplete>
      </Section>

      <Section title="Directeur de la publication">
        <ToComplete>
          <strong>À compléter avant toute publication.</strong> Nom et qualité de la personne
          physique responsable de la publication.
        </ToComplete>
      </Section>

      <Section title="Hébergement">
        <ToComplete>
          <strong>À compléter avant toute publication.</strong> Dénomination, adresse et téléphone
          de l’hébergeur de l’application et de la base de données.
        </ToComplete>
      </Section>

      <Section title="Nature du service">
        <p>
          MapFeux est un service d’information cartographique indépendant. Il ne constitue ni un
          système d’alerte, ni une source de confirmation terrain, ni un outil de commandement. Il
          n’est rattaché à aucun service d’incendie et de secours, à aucune préfecture et à aucune
          administration.
        </p>
        <p>
          Les observations satellitaires, traitements algorithmiques et estimations affichés peuvent
          être retardés, incomplets ou incertains. Les consignes et publications des autorités
          restent prioritaires en toute circonstance.
        </p>
      </Section>

      <Section title="Propriété des données">
        <p>
          Les données affichées appartiennent à leurs producteurs respectifs et restent soumises à
          leurs licences. Le détail figure sur la page Sources et licences.
        </p>
      </Section>

      <Section title="Signaler une erreur">
        <ToComplete>
          <strong>À compléter avant toute publication.</strong> Adresse de contact permettant de
          signaler une information erronée. Le cahier en fait un critère de mise en service : un
          service qui publie des informations doit pouvoir être corrigé.
        </ToComplete>
      </Section>
    </Prose>
  );
}
