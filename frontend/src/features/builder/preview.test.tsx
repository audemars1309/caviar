import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { ResumePreview } from "@/features/builder/components/ResumePreview";

const content = {
  PERSONAL_INFO: { full_name: "Dharun Raj", email: "d@example.com" },
  SUMMARY: { text: "Backend engineer building Caviar." },
  EXPERIENCE: {
    entries: [
      {
        company: "Acme",
        title: "Engineer",
        location: null,
        start_date: "Jan 2024",
        end_date: "Present",
        bullets: ["Built the resume pipeline"],
      },
    ],
  },
  SKILLS: { groups: [{ name: "Languages", skills: ["Python", "TypeScript"] }] },
};

describe("ResumePreview", () => {
  it("renders backend-shaped content in resume order", () => {
    render(<ResumePreview content={content} />);
    expect(screen.getByRole("article", { name: /resume preview/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Dharun Raj" })).toBeInTheDocument();
    expect(screen.getByText("Backend engineer building Caviar.")).toBeInTheDocument();
    expect(screen.getByText("Built the resume pipeline")).toBeInTheDocument();
    expect(screen.getByText(/Python, TypeScript/)).toBeInTheDocument();
    // The preview is explicit that the backend PDF is authoritative.
    expect(screen.getByText(/generated PDF is authoritative/i)).toBeInTheDocument();
  });

  it("supports zoom in and out within bounds", async () => {
    const user = userEvent.setup();
    render(<ResumePreview content={content} />);
    expect(screen.getByText("80%")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /zoom in/i }));
    expect(screen.getByText("100%")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /zoom out/i }));
    await user.click(screen.getByRole("button", { name: /zoom out/i }));
    await user.click(screen.getByRole("button", { name: /zoom out/i }));
    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /zoom out/i })).toBeDisabled();
  });

  it("omits sections without content", () => {
    render(<ResumePreview content={{ PERSONAL_INFO: { full_name: "A" } }} />);
    expect(screen.queryByText("Experience")).not.toBeInTheDocument();
    expect(screen.queryByText("Skills")).not.toBeInTheDocument();
  });
});
