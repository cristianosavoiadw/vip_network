import { Link, useRouteError } from "react-router-dom";
import { AlertTriangle } from "lucide-react";

/** Shown instead of a blank/technical screen when a page breaks. */
export function RouteError() {
  const error = useRouteError();
  if (import.meta.env.DEV) console.error(error);
  return (
    <div className="grid min-h-[60vh] place-items-center p-6">
      <div className="panel flex max-w-[520px] flex-col items-center gap-3 px-6 py-10 text-center">
        <AlertTriangle size={36} className="text-warn" />
        <h2 className="text-lg">Algo deu errado nesta página</h2>
        <p className="text-ink-muted">Tente recarregar. Se continuar, fale com a equipe VIP Network e diga em qual tela aconteceu.</p>
        <div className="flex flex-wrap justify-center gap-2">
          <button type="button" className="btn btn-gold btn-sm" onClick={() => window.location.reload()}>
            Recarregar
          </button>
          <Link to="/app" className="btn btn-outline btn-sm">
            Ir para a Visão Geral
          </Link>
        </div>
      </div>
    </div>
  );
}
