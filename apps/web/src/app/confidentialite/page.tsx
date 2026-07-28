import type { Metadata } from 'next';

import { Prose, Section, ToComplete } from '@/components/prose';

/**
 * Politique de confidentialité. Cahier §22.1 et §22.2.
 *
 * Le contenu décrit l'architecture réellement en place, vérifiable dans le
 * dépôt : aucun compte public, aucune coordonnée conservée, aucun traceur. Ce
 * qui relève d'une décision d'éditeur non encore prise est signalé comme tel
 * plutôt que rédigé au conditionnel.
 */

export const metadata: Metadata = {
  title: 'Confidentialité',
  description:
    'Quelles données MapFeux collecte, lesquelles il ne collecte pas, et ce qu’il advient de votre position.',
};

export default function PrivacyPage() {
  return (
    <Prose
      title="Confidentialité"
      lead="Ce que le service sait de vous : très peu, et cela se vérifie."
    >
      <Section title="Aucun compte, aucun profil">
        <p>
          MapFeux ne propose pas de compte au public. Il n’y a ni inscription, ni favoris, ni
          notifications, donc aucun profil d’utilisateur. Seuls les administrateurs du service
          disposent d’un compte.
        </p>
      </Section>

      <Section title="Votre position n’est pas conservée">
        <p>
          La fonction « autour de moi » demande votre position au navigateur, et seulement après que
          vous l’avez déclenchée. Les coordonnées sont envoyées au serveur pour déterminer la
          commune qui les contient, puis la réponse ne contient que cette commune.
        </p>
        <p>
          Les coordonnées ne sont écrites ni en base, ni dans les journaux techniques. Elles sont
          transmises dans le corps de la requête et non dans l’adresse, parce que les adresses
          consultées se retrouvent dans les journaux d’accès des intermédiaires réseau.
        </p>
      </Section>

      <Section title="Journaux techniques">
        <p>
          Le service enregistre des journaux d’exploitation : horodatage, page demandée, code de
          réponse, durée. Ils servent à diagnostiquer les pannes. Aucune clé, aucun contenu de
          requête sensible et aucune coordonnée géographique n’y figurent.
        </p>
      </Section>

      <Section title="Cookies et mesure d’audience">
        <p>
          Le service ne dépose aucun cookie de mesure d’audience ni de publicité. Un cookie
          technique n’est utilisé que pour la session des administrateurs connectés.
        </p>
        <ToComplete>
          <strong>À arbitrer avant l’ouverture au public.</strong> Si une mesure d’audience est
          ajoutée, elle devra être sans cookie, ou soumise à un consentement dont le refus est aussi
          simple que l’acceptation. Cette page devra alors être mise à jour.
        </ToComplete>
      </Section>

      <Section title="Hébergement et sous-traitants">
        <ToComplete>
          <strong>À compléter par l’éditeur.</strong> La liste des sous-traitants — hébergeur de
          l’application, hébergeur de la base de données, réseau de diffusion — et leur région
          d’hébergement doivent être nommés ici, avec la durée de conservation des journaux.
        </ToComplete>
      </Section>

      <Section title="Vos droits">
        <ToComplete>
          <strong>À compléter par l’éditeur.</strong> Adresse de contact pour l’exercice des droits
          d’accès, de rectification et d’effacement, et modalités de réclamation auprès de la CNIL.
        </ToComplete>
      </Section>
    </Prose>
  );
}
