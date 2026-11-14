import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { ApiError } from "@/lib/api";
import { Empty, ErrorBox, Spinner } from "@/components/ui/bits";
import { CompanyProfile, useCompany } from "@/features/discover/CompanyDrawer";
import { IntentModal } from "@/features/discover/IntentModal";
import type { IntentTarget } from "@/features/discover/IntentModal";

/** /app/empresas/:slug — the company's page inside the network (public profile, offers, published
 *  needs, relationship state and actions). */
export default function CompanyPage() {
  const { slug = "" } = useParams();
  const navigate = useNavigate();
  const q = useCompany(slug);
  const [target, setTarget] = useState<IntentTarget | null>(null);

  return (
    <div className="mx-auto flex w-full max-w-[860px] flex-col gap-4">
      <button type="button" onClick={() => (window.history.length > 1 ? navigate(-1) : navigate("/app/descobrir"))} className="inline-flex items-center gap-1.5 self-start text-sm font-semibold text-ink-muted hover:text-ink">
        <ArrowLeft size={16} /> Voltar
      </button>
      {q.isLoading ? (
        <Spinner />
      ) : q.error ? (
        q.error instanceof ApiError && q.error.status === 404 ? (
          <div className="panel">
            <Empty title="Empresa não encontrada" action={<Link to="/app/descobrir" className="btn btn-outline btn-sm">Descobrir empresas</Link>}>
              O perfil pode ter sido removido ou não está disponível para sua empresa.
            </Empty>
          </div>
        ) : (
          <ErrorBox error={q.error} retry={() => q.refetch()} />
        )
      ) : q.data ? (
        <section className="panel overflow-hidden">
          <CompanyProfile d={q.data} variant="page" onLike={setTarget} onBlocked={() => q.refetch()} />
        </section>
      ) : null}
      <IntentModal target={target} onClose={() => setTarget(null)} onLiked={() => setTarget(null)} />
    </div>
  );
}
