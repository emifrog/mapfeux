import { DETECTION_PIXEL_NOTICE, MAP_DISCLAIMER } from '@mapfeux/domain';
import type { Metadata } from 'next';
import Link from 'next/link';

import { Prose, Section } from '@/components/prose';

/**
 * Page méthodologie. Cahier §7.1 et §28.1.
 *
 * C'est la page qui rend le service défendable. Elle explique comment une
 * détection devient un événement, et surtout ce que le service ne sait pas.
 * Chaque phrase doit rester vraie sans être vérifiée par le lecteur — c'est
 * l'inverse d'une page marketing.
 */

export const metadata: Metadata = {
  title: 'Méthodologie',
  description:
    'Comment MapFeux passe d’une détection thermique satellitaire à un événement, et ce que le service ne peut pas dire.',
};

export default function MethodologyPage() {
  return (
    <Prose
      title="Méthodologie"
      lead="Comment une détection satellitaire devient un événement, et ce que cela ne dit pas."
    >
      <Section title="Ce qu’observe un satellite">
        <p>
          Les satellites d’observation de la Terre embarquent des capteurs infrarouges qui mesurent
          la température de la surface. Lorsqu’un point du sol est nettement plus chaud que son
          environnement, l’algorithme de la NASA le signale comme <em>anomalie thermique</em>.
        </p>
        <p>{MAP_DISCLAIMER}</p>
        <p>
          Une anomalie thermique peut être un feu de végétation, mais aussi une torchère
          industrielle, un four, un brûlage agricole, un volcan, ou un reflet du soleil sur une
          surface métallique. MapFeux affiche l’observation, pas son interprétation.
        </p>
      </Section>

      <Section title="Trois limites qui ne se corrigent pas">
        <p>
          <strong>Le satellite passe, il ne surveille pas.</strong> Les capteurs utilisés sont en
          orbite polaire : ils survolent la France quelques fois par jour seulement. Entre deux
          passages, aucune information nouvelle n’arrive. Un feu qui démarre juste après un passage
          peut rester invisible plusieurs heures.
        </p>
        <p>
          <strong>Les nuages masquent le sol.</strong> L’infrarouge thermique ne traverse pas une
          couverture nuageuse épaisse. Une absence de détection sous les nuages ne signifie rien.
        </p>
        <p>
          <strong>La résolution est grossière.</strong> Un pixel VIIRS couvre environ 375 mètres de
          côté, un pixel MODIS environ un kilomètre. {DETECTION_PIXEL_NOTICE} Un feu plus petit que
          le pixel peut être détecté s’il est très chaud, ou passer inaperçu s’il ne l’est pas.
        </p>
      </Section>

      <Section title="Du point à l’événement">
        <p>
          Les détections proches dans l’espace et dans le temps sont regroupées automatiquement en
          un <em>événement probable</em>. Le rapprochement combine la distance et le délai : la
          tolérance spatiale s’élargit avec le temps écoulé, parce qu’un feu s’étend, mais elle est
          plafonnée pour que deux foyers distincts d’une même vallée ne soient pas confondus.
        </p>
        <p>
          Ce regroupement est une <strong>inférence</strong>, pas une observation. Il peut réunir
          deux feux voisins en un seul événement, ou séparer un même feu en deux. C’est pourquoi la
          fiche indique la provenance de chaque bloc d’information.
        </p>
        <p>
          L’algorithme est déterministe : rejouer le calcul sur les mêmes données produit exactement
          le même résultat. Sa version est enregistrée avec chaque rattachement, de sorte qu’un
          regroupement ancien reste explicable après un changement de réglage.
        </p>
      </Section>

      <Section title="Les trois statuts, et pourquoi ils ne se confondent pas">
        <p>
          Une fiche affiche trois informations que l’on pourrait croire redondantes, et qui
          répondent à trois questions différentes.
        </p>
        <p>
          <strong>La fraîcheur technique</strong> dit quand remonte la dernière observation
          satellitaire. Elle ne dit rien de l’état du phénomène : l’absence d’observation récente
          peut signifier que le feu est éteint, ou simplement qu’aucun satellite n’est repassé.
        </p>
        <p>
          <strong>Le niveau de vérification</strong> dit ce que l’on sait de l’existence de
          l’événement : une simple détection, un regroupement cohérent, une mention publique, ou une
          confirmation par une autorité.
        </p>
        <p>
          <strong>Le statut officiel</strong> — feu fixé, maîtrisé, éteint — n’apparaît que s’il a
          été publié par une autorité, avec sa source et sa date. Aucun traitement automatique ne
          peut le renseigner. Cette règle est appliquée dans la base de données elle-même, pas
          seulement dans l’interface.
        </p>
      </Section>

      <Section title="La fiabilité ne mesure pas la gravité">
        <p>
          Chaque événement porte un niveau de fiabilité — faible, modéré, élevé. Il agrège la
          confiance donnée par le fournisseur, la répétition des observations, la présence de
          plusieurs capteurs indépendants et la persistance dans le temps.
        </p>
        <p>
          Une fiabilité élevée signifie <em>l’observation est solide</em>, jamais{' '}
          <em>le feu est important</em>. MapFeux ne connaît ni la surface parcourue, ni l’intensité
          au sol, ni les moyens engagés.
        </p>
      </Section>

      <Section title="Ce que MapFeux ne fera jamais">
        <p>
          Confirmer qu’un incendie est en cours. Déclarer qu’un feu est éteint. Publier la position
          de moyens ou de personnels. Émettre une alerte de sécurité civile. Reformuler une
          information officielle.
        </p>
        <p>
          Pour les consignes, les évacuations et les fermetures d’accès, la préfecture et votre
          commune font foi. Les liens utiles figurent sur chaque page de territoire.
        </p>
      </Section>

      <Section title="Aller plus loin">
        <p>
          Le détail des sources, de leurs licences et de leur fraîcheur se trouve sur les pages{' '}
          <Link href="/sources" className="underline underline-offset-4">
            Sources
          </Link>{' '}
          et{' '}
          <Link href="/statut" className="underline underline-offset-4">
            État des données
          </Link>
          .
        </p>
      </Section>
    </Prose>
  );
}
