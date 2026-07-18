import { Link } from "react-router-dom";

import { EmptyState } from "../shared/ui/async-state";

export function NotFoundPage() {
  return (
    <EmptyState
      title="This page does not exist"
      action={
        <Link className="button-primary" to="/">
          Return to workspace
        </Link>
      }
    >
      <p>The requested CodexForge page could not be found.</p>
    </EmptyState>
  );
}
