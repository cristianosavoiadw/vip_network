import { CONTACT_EMAIL, LegalDoc, Sec } from "@/features/legal/LegalDoc";

export default function PrivacyPage() {
  return (
    <LegalDoc eyebrow="LGPD" title="Política de privacidade" updated="14/11/2026">
      <p>
        Esta política explica, de forma simples, quais dados a VIP Network trata, para quê, com quem compartilha e como você exerce seus direitos, conforme a Lei Geral de Proteção de
        Dados (Lei nº 13.709/2018).
      </p>
      <Sec title="1. Dados que tratamos">
        <ul>
          <li><b>Da empresa:</b> CNPJ e dados oficiais públicos (razão social, CNAE, endereço, situação cadastral), perfil público, produtos e serviços oferecidos, o que a empresa compra e objetivos comerciais.</li>
          <li><b>Das pessoas:</b> nome, cargo, e-mail profissional, telefone, departamento, senha (guardada de forma cifrada) e registros de acesso.</li>
          <li><b>De uso:</b> curtidas, conexões, mensagens, inscrições em eventos e preferências de notificação.</li>
          <li><b>De pagamento:</b> o cartão fica com a Stripe. Guardamos apenas a bandeira, os quatro últimos dígitos e a validade para mostrar a você.</li>
        </ul>
      </Sec>
      <Sec title="2. Para que usamos">
        <ul>
          <li>Criar e manter a conta da empresa e o acesso de cada pessoa (execução de contrato).</li>
          <li>Mostrar o perfil público e recomendar empresas compatíveis (execução de contrato e legítimo interesse).</li>
          <li>Cobrar a assinatura e emitir faturas (execução de contrato e obrigação legal).</li>
          <li>Enviar e-mails de serviço e, se você permitir, avisos de oportunidades e eventos (consentimento, que pode ser retirado a qualquer momento em Notificações).</li>
          <li>Prevenir fraudes e manter a segurança da plataforma (legítimo interesse).</li>
        </ul>
      </Sec>
      <Sec title="3. O que fica privado">
        <p>
          O que sua empresa vende pode ser divulgado publicamente. O que sua empresa compra é privado e somente será utilizado para identificar oportunidades comerciais para sua
          organização, conforme suas preferências de privacidade. Outras empresas não veem preços pagos, volumes nem fornecedores atuais. Uma curtida revela apenas a empresa que curtiu e o
          interesse declarado. Bloqueios valem nos dois sentidos.
        </p>
      </Sec>
      <Sec title="4. Inteligência artificial">
        <p>
          Usamos inteligência artificial para sugerir descrições de perfil, calcular compatibilidade e indicar oportunidades. Sugestões só entram no perfil depois da aprovação de alguém da
          empresa. Dados de mentoria não são usados em recomendações.
        </p>
      </Sec>
      <Sec title="5. Com quem compartilhamos">
        <ul>
          <li>Stripe, para processar pagamentos.</li>
          <li>Provedores de infraestrutura, e-mail e consulta de CNPJ, contratados com cláusulas de proteção de dados.</li>
          <li>Autoridades, quando a lei exigir.</li>
        </ul>
        <p>Não vendemos dados pessoais.</p>
      </Sec>
      <Sec title="6. Por quanto tempo guardamos">
        <p>
          Enquanto a conta estiver ativa e, depois, pelo prazo exigido por lei (por exemplo, registros fiscais e de acesso). Ao fim desse prazo, os dados são excluídos ou anonimizados.
        </p>
      </Sec>
      <Sec title="7. Seus direitos">
        <p>
          Você pode pedir confirmação do tratamento, acesso, correção, anonimização, portabilidade, exclusão de dados tratados com consentimento, informação sobre compartilhamento e
          revisão de decisões automatizadas. Basta escrever para <span className="select-all font-semibold text-ink">{CONTACT_EMAIL}</span>. Respondemos em até 15 dias.
        </p>
      </Sec>
      <Sec title="8. Segurança">
        <p>
          Usamos conexão cifrada, senhas guardadas com algoritmo de hash, controle de acesso por departamento e registro das ações importantes. Se houver um incidente que possa trazer
          risco, avisamos as pessoas afetadas e a Autoridade Nacional de Proteção de Dados (ANPD).
        </p>
      </Sec>
      <Sec title="9. Cookies">
        <p>Usamos apenas cookies necessários para manter você conectado com segurança. Não usamos cookies de publicidade.</p>
      </Sec>
    </LegalDoc>
  );
}
