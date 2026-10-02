import { SignInView } from "./SignInView";

export default async function SignInPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const { error } = await searchParams;
  return (
    <SignInView
      initialError={error ? "Sign-in didn't complete. Please try again." : null}
    />
  );
}
