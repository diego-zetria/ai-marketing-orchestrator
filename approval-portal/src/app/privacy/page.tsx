export default function PrivacyPage() {
  return (
    <main className="min-h-screen bg-background px-4 py-12">
      <div className="mx-auto max-w-3xl prose prose-sm dark:prose-invert">
        <h1 className="text-2xl font-bold text-foreground">
          Política de Privacidade
        </h1>
        <p className="text-sm text-muted-foreground">
          Última atualização: 28 de fevereiro de 2026
        </p>

        <h2>1. Introdução</h2>
        <p>
          A Agência Agency (&quot;nós&quot;, &quot;nosso&quot;) opera o aplicativo de
          gestão de conteúdo e aprovação de materiais digitais. Esta Política de
          Privacidade descreve como coletamos, usamos e protegemos suas informações.
        </p>

        <h2>2. Dados Coletados</h2>
        <ul>
          <li>
            <strong>Dados de conta:</strong> nome, e-mail e identificadores de
            plataformas integradas (ClickUp, Instagram, Telegram).
          </li>
          <li>
            <strong>Dados de conteúdo:</strong> materiais enviados para revisão e
            aprovação, comentários e histórico de versões.
          </li>
          <li>
            <strong>Dados de uso:</strong> métricas de desempenho de publicações em
            redes sociais (alcance, visualizações, interações) obtidas via Instagram
            Graph API.
          </li>
        </ul>

        <h2>3. Uso dos Dados</h2>
        <p>Utilizamos os dados coletados para:</p>
        <ul>
          <li>Gerenciar o fluxo de aprovação de conteúdo entre equipe e clientes.</li>
          <li>Gerar relatórios de desempenho e análises de performance.</li>
          <li>Enviar notificações sobre status de tarefas e aprovações.</li>
          <li>Melhorar nossos serviços e processos internos.</li>
        </ul>

        <h2>4. Compartilhamento de Dados</h2>
        <p>
          Não vendemos nem compartilhamos seus dados pessoais com terceiros, exceto:
        </p>
        <ul>
          <li>Provedores de infraestrutura (AWS) para hospedagem segura.</li>
          <li>APIs de plataformas integradas (Meta/Instagram, ClickUp) conforme necessário para o funcionamento do serviço.</li>
          <li>Quando exigido por lei ou ordem judicial.</li>
        </ul>

        <h2>5. Segurança</h2>
        <p>
          Empregamos medidas técnicas e organizacionais para proteger seus dados,
          incluindo criptografia em trânsito (TLS), controle de acesso e
          armazenamento seguro em infraestrutura AWS.
        </p>

        <h2>6. Retenção de Dados</h2>
        <p>
          Os dados são retidos enquanto necessários para a prestação do serviço.
          Você pode solicitar a exclusão dos seus dados a qualquer momento.
        </p>

        <h2>7. Seus Direitos</h2>
        <p>
          Conforme a LGPD (Lei Geral de Proteção de Dados), você tem direito a:
        </p>
        <ul>
          <li>Acessar seus dados pessoais.</li>
          <li>Solicitar correção de dados incompletos ou inexatos.</li>
          <li>Solicitar exclusão dos seus dados.</li>
          <li>Revogar consentimento a qualquer momento.</li>
        </ul>

        <h2>8. Contato</h2>
        <p>
          Para questões sobre privacidade, entre em contato pelo e-mail:{" "}
          <a href="mailto:contato@agenciaapp.com.br">contato@agenciaapp.com.br</a>
        </p>

        <div className="mt-8 border-t pt-6">
          <p className="text-xs text-muted-foreground">
            Agência Agency — Portal de Aprovação
          </p>
        </div>
      </div>
    </main>
  );
}
