import { useEffect, useState } from "react";

import { OVERVIEW_PROJECT_CHANGE_EVENT, readOverviewActiveProject } from "./overview-project";

export function useOverviewActiveProject() {
  const [activeProject, setActiveProject] = useState(() => readOverviewActiveProject());

  useEffect(() => {
    const syncProject = () => {
      setActiveProject(readOverviewActiveProject());
    };

    window.addEventListener(OVERVIEW_PROJECT_CHANGE_EVENT, syncProject);
    window.addEventListener("storage", syncProject);
    return () => {
      window.removeEventListener(OVERVIEW_PROJECT_CHANGE_EVENT, syncProject);
      window.removeEventListener("storage", syncProject);
    };
  }, []);

  return activeProject;
}
