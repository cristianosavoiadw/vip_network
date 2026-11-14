import { useParams } from "react-router-dom";
import { InviteLanding } from "@/features/signup/InviteLanding";
import { readInviteCode } from "@/features/signup/inviteStore";

/** /convite and /convite/:code: validates the code and sends the company to the sign-up. */
export default function InvitePage() {
  const { code } = useParams();
  return <InviteLanding key={code ?? ""} initialCode={code ?? readInviteCode() ?? ""} />;
}
