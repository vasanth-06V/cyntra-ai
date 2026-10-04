// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AppError from "./error";
import NotFound from "./not-found";
import DashboardLoading from "./(dashboard)/loading";
import SignUpPage from "./(auth)/sign-up/page";
import { SignInView } from "./(auth)/sign-in/SignInView";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
  notFound: () => {
    throw new Error("NEXT_NOT_FOUND");
  },
}));
vi.mock("@/lib/supabase/client", () => ({ createClient: () => ({ auth: {} }) }));

afterEach(() => vi.unstubAllEnvs());

describe("error boundary", () => {
  it("offers a retry that calls retry() and a way back home", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const retry = vi.fn();
    render(<AppError error={Object.assign(new Error("boom"), { digest: "abc123" })} retry={retry} />);
    expect(screen.getByRole("heading", { name: "Something went wrong" })).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("abc123");
    await userEvent.setup().click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("link", { name: "Go to the home page" })).toHaveAttribute("href", "/");
  });
});

describe("not-found page", () => {
  it("explains and links home", () => {
    render(<NotFound />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/can.t find that page/i);
    expect(screen.getByRole("link", { name: "Go to the home page" })).toHaveAttribute("href", "/");
  });
});

describe("dashboard loading state", () => {
  it("announces loading once", () => {
    render(<DashboardLoading />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading");
  });
});

describe("demo sign-up gating (M-2)", () => {
  it("is a 404 in production builds and hides the sign-in link", () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("NEXT_PUBLIC_ENABLE_DEMO_SIGNUP", "");
    expect(() => SignUpPage()).toThrow("NEXT_NOT_FOUND");
    render(<SignInView />);
    expect(screen.queryByRole("link", { name: /demo account/i })).not.toBeInTheDocument();
  });

  it("is available (and linked) outside production", () => {
    vi.stubEnv("NODE_ENV", "development");
    expect(() => SignUpPage()).not.toThrow();
    render(<SignInView />);
    expect(screen.getByRole("link", { name: /demo account/i })).toHaveAttribute("href", "/sign-up");
  });

  it("can be turned on in production explicitly", () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("NEXT_PUBLIC_ENABLE_DEMO_SIGNUP", "true");
    expect(() => SignUpPage()).not.toThrow();
  });
});
