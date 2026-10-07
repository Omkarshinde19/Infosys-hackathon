/** Register only the chart features the dashboard actually uses. */
import { init, use as registerCharts } from "echarts/core";
import { BarChart, LineChart } from "echarts/charts";
import { GridComponent, LegendComponent, TitleComponent, ToolboxComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
registerCharts([BarChart, LineChart, GridComponent, LegendComponent, TitleComponent, ToolboxComponent, TooltipComponent, CanvasRenderer]);
export { init };
export type { ECharts, EChartsOption } from "echarts";
