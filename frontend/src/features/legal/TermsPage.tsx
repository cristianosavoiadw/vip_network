import { Link } from "react-router-dom";
import { CONTACT_EMAIL, LegalDoc, Sec } from "@/features/legal/LegalDoc";

export default function TermsPage() {
  return (
    <LegalDoc eyebrow="Institucional" title="Termos de uso" updated="14/11/2026">
      <p>
        Estes termos explicam como funciona a VIP Network, a rede que conecta empresas para comprar, vender e fazer parcerias. Ao criar uma conta, a empresa e cada pessoa que usa a
        plataforma concordam com estas regras.
      </p>
      <Sec title="1. Quem pode usar">
        <p>
          A VIP Network é para empresas com CNPJ ativo. Quem faz o cadastro declara ter autorização para representar a empresa. Cada CNPJ tem uma única conta; outras pessoas da empresa
          entram por convite do responsável ou por pedido de acesso aprovado por ele.
        </p>
      </Sec>
      <Sec title="2. Conta e equipe">
        <ul>
          <li>Cada pessoa tem acesso próprio, com e-mail e senha pessoais. Não compartilhe sua senha.</li>
          <li>O que cada pessoa vê depende do departamento dela (Diretoria, Comercial, Compras, Financeiro, RH ou departamentos criados pela empresa).</li>
          <li>O responsável pela conta pode convidar, bloquear ou remover pessoas a qualquer momento.</li>
        </ul>
      </Sec>
      <Sec title="3. Assinatura, teste grátis e cancelamento">
        <ul>
          <li>O plano pode ser mensal ou anual. Cada CNPJ tem direito a um único período de teste grátis de 7 dias (168 horas).</li>
          <li>O cartão é cadastrado no início. A primeira cobrança acontece no fim do teste, na data e no valor mostrados antes da confirmação.</li>
          <li>Cancelando durante o teste, nada é cobrado. Cancelando depois, o acesso continua até o fim do período já pago, sem reembolso proporcional.</li>
          <li>Empresas que entram por convite recebem o Plano VIP Convidado pelo prazo informado no convite. As regras depois desse prazo aparecem na tela antes da confirmação.</li>
          <li>Os pagamentos são processados com segurança pela Stripe. A VIP Network não guarda o número do cartão.</li>
        </ul>
      </Sec>
      <Sec title="4. Informações da empresa">
        <ul>
          <li>Os dados oficiais do CNPJ vêm de fontes públicas e não podem ser editados pela empresa.</li>
          <li>O perfil público, os produtos e os serviços que a empresa vende são de responsabilidade dela e podem ser vistos por outras empresas da rede.</li>
          <li>O que a empresa compra é privado: serve só para encontrar oportunidades para ela, conforme as preferências de privacidade.</li>
          <li>Sugestões feitas por inteligência artificial só entram no perfil depois de aprovadas por alguém da empresa.</li>
        </ul>
      </Sec>
      <Sec title="5. Conduta">
        <p>
          Não é permitido publicar informação falsa, enviar mensagens abusivas ou em massa, oferecer produtos ilegais ou usar dados de outras empresas fora da plataforma sem autorização.
          Qualquer empresa pode bloquear outra ou denunciar um conteúdo. A equipe pode suspender contas que descumpram estes termos.
        </p>
      </Sec>
      <Sec title="6. Recomendações e destaque pago">
        <p>
          As recomendações e a compatibilidade são calculadas pela plataforma e servem como orientação; não garantimos negócios. O Brilhar na Rede aumenta a exposição nas áreas
          patrocinadas, não altera a compatibilidade calculada e não garante visualizações nem vendas.
        </p>
      </Sec>
      <Sec title="7. Negociações entre empresas">
        <p>
          A VIP Network aproxima empresas. Preços, contratos, entregas e pagamentos combinados entre elas são responsabilidade exclusiva das empresas envolvidas.
        </p>
      </Sec>
      <Sec title="8. Privacidade">
        <p>
          O tratamento de dados pessoais segue a Lei Geral de Proteção de Dados (LGPD) e está descrito na nossa <Link to="/privacidade" className="font-semibold text-gold-ink">Política de privacidade</Link>.
        </p>
      </Sec>
      <Sec title="9. Mudanças e contato">
        <p>
          Podemos atualizar estes termos. Mudanças importantes são avisadas por e-mail ou na plataforma antes de valer. Dúvidas: <span className="select-all font-semibold text-ink">{CONTACT_EMAIL}</span>.
        </p>
      </Sec>
    </LegalDoc>
  );
}
