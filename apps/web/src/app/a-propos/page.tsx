import type { Metadata } from 'next';
import Link from 'next/link';

import { Prose, Section, ToComplete } from '@/components/prose';

/**
 * Page de présentation. Cahier §7.1.
 *
 * Elle dit ce qu'est le service et, tout aussi important, ce qu'il n'est pas.
 * L'ambiguïté sur ce point est le principal risque du projet : une carte de
 * feux prise pour une source officielle produit exactement la confusion
 * qu'elle prétendait dissiper.
 */

export const metadata: Metadata = {
  title: 'À propos',
  description: 'Ce qu’est MapFeux, ce qu’il n’est pas, et pourquoi il existe.',
};

export default function AboutPage() {
  return (
    <Prose
      title="À propos"
      lead="Une page de référence par événement : permanente, sourcée, horodatée, et lisible même quand le reste tombe."
    >
      <Section title="Pourquoi ce service">
        <p>
          Les détections thermiques satellitaires sont publiques et gratuites depuis des années.
          Elles sont aussi diffusées sous une forme difficile à lire pour qui n’en connaît pas les
          limites : des points sur une carte mondiale, sans commune, sans heure locale, sans
          explication de ce qu’un point signifie réellement.
        </p>
        <p>
          MapFeux ne produit aucune donnée nouvelle. Il rend lisible ce qui existe déjà, à la maille
          communale, en français, en indiquant systématiquement qui a observé quoi et quand.
        </p>
      </Section>

      <Section title="Ce que le service n’est pas">
        <p>
          Ce n’est pas un système d’alerte. Il ne prévient personne, ne déclenche rien et ne
          remplace aucun canal officiel.
        </p>
        <p>
          Ce n’est pas une source de confirmation. Une détection thermique n’est pas un incendie
          confirmé, et l’absence de détection n’est pas l’absence de feu.
        </p>
        <p>
          Ce n’est pas un outil opérationnel. Aucune donnée de moyens, de personnels ou
          d’intervention n’y figure, et aucune n’y figurera.
        </p>
        <p>
          MapFeux n’est rattaché à aucun service d’incendie et de secours, à aucune préfecture et à
          aucune administration.
        </p>
      </Section>

      <Section title="Comment il est fait">
        <p>
          Le service applique quelques règles strictes : la donnée brute reçue d’un fournisseur
          n’est jamais modifiée ; toute information affichée porte sa provenance et son horodatage ;
          un traitement automatique ne peut jamais produire une confirmation officielle ; et une
          correction n’efface jamais ce qu’elle corrige.
        </p>
        <p>
          Le détail est sur la page{' '}
          <Link href="/methodologie" className="underline underline-offset-4">
            Méthodologie
          </Link>
          .
        </p>
      </Section>

      <Section title="Qui le publie">
        <ToComplete>
          <strong>À compléter avant toute publication.</strong> Identité de l’éditeur, modèle de
          financement, et réponse à la question de la continuité du service. Le cahier en fait une
          condition de mise en service : un service d’information doit dire qui le tient et ce qu’il
          devient si son auteur s’arrête.
        </ToComplete>
      </Section>
    </Prose>
  );
}
