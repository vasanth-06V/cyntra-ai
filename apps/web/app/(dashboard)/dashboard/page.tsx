import { requireUser } from "@/lib/auth/guards";
import { Card } from "@/components/ui/Card";

export default async function DashboardHomePage() {
  const { role } = await requireUser();

  return (
    <div>
      <h1 className="text-2xl font-semibold">Welcome to CyntraAI</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Signed in as <span className="font-medium">{role}</span>.
      </p>

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card className="p-5">
          <h2 className="font-medium">AI Chatbot</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Chat with any provider you&apos;ve configured.
          </p>
        </Card>
        <Card className="p-5">
          <h2 className="font-medium">Interviewing Agent</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Voice-driven mock interviews, personalized to your resume.
          </p>
        </Card>
        <Card className="p-5">
          <h2 className="font-medium">ATS Score</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            See how your resume matches a job description.
          </p>
        </Card>
      </div>
    </div>
  );
}
