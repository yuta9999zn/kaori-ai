import { setupWorker } from "msw/browser";
import { authHandlers }       from "./handlers/auth";
import { dashboardHandlers }  from "./handlers/dashboard";
import { pipelineHandlers }   from "./handlers/pipeline";
import { analyticsHandlers }  from "./handlers/analytics";
import { enterpriseHandlers } from "./handlers/enterprise";
import { platformHandlers }   from "./handlers/platform";
import { decisionsHandlers }    from "./handlers/decisions";
import { subscriptionHandlers } from "./handlers/subscription";
import { chatHandlers }         from "./handlers/chat";
import { reportsHandlers }      from "./handlers/reports";
import { alertsHandlers }       from "./handlers/alerts";
import { frameworksHandlers }   from "./handlers/frameworks";
import { northStarHandlers }    from "./handlers/north_star";
import { risksHandlers }        from "./handlers/risks";
import { dataExplorerHandlers } from "./handlers/data_explorer";
import { strategyHandlers }     from "./handlers/strategy";
import { multiTierHandlers }    from "./handlers/multi_tier";
import { explainabilityHandlers } from "./handlers/explainability";
import { knowledgeHandlers }     from "./handlers/knowledge";

export const worker = setupWorker(
  ...authHandlers,
  ...dashboardHandlers,
  ...pipelineHandlers,
  ...analyticsHandlers,
  ...enterpriseHandlers,
  ...platformHandlers,
  ...decisionsHandlers,
  ...subscriptionHandlers,
  ...chatHandlers,
  ...reportsHandlers,
  ...alertsHandlers,
  ...frameworksHandlers,
  ...northStarHandlers,
  ...risksHandlers,
  ...dataExplorerHandlers,
  ...strategyHandlers,
  ...multiTierHandlers,
  ...explainabilityHandlers,
  ...knowledgeHandlers,
);
