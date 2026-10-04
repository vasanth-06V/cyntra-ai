// TEMPORARY DEV/DEMO ROUTE -- see DemoSignUpView.tsx. Hidden (404) in production
// builds unless NEXT_PUBLIC_ENABLE_DEMO_SIGNUP=true. Delete alongside the view
// once Google sign-in is live and verified end-to-end.
import { notFound } from "next/navigation";
import { demoSignUpEnabled } from "@/lib/demo-signup";
import { DemoSignUpView } from "./DemoSignUpView";

export const metadata = { title: "Create account" };

export default function SignUpPage() {
  if (!demoSignUpEnabled()) notFound();
  return <DemoSignUpView />;
}
