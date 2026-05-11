import { useEffect, useState } from "react";

import { GUIDE_STATE_CHANGED_EVENT, readGuideState, type GuideStateV2 } from "./guide-flow";

export function useGuideState() {
  const [guideState, setGuideState] = useState<GuideStateV2>(() => readGuideState());

  useEffect(() => {
    const syncGuideState = () => {
      setGuideState(readGuideState());
    };

    window.addEventListener(GUIDE_STATE_CHANGED_EVENT, syncGuideState);
    window.addEventListener("storage", syncGuideState);
    return () => {
      window.removeEventListener(GUIDE_STATE_CHANGED_EVENT, syncGuideState);
      window.removeEventListener("storage", syncGuideState);
    };
  }, []);

  return guideState;
}
