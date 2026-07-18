import { createBrowserRouter } from "react-router-dom";

import { AppShell } from "./layout/app-shell";
import { DashboardPage } from "../pages/dashboard-page";
import { NotFoundPage } from "../pages/not-found-page";
import { RunDetailPage } from "../pages/run-detail-page";

export const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "runs/:runId", element: <RunDetailPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
