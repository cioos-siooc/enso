/**
 * ECharts with only what the two charts draw, registered once.
 *
 * `import * as echarts from 'echarts'` pulls in every chart type, component and
 * both renderers. The time series is lines with a visualMap, a legend, mark
 * lines and dataZoom; the ranking is one custom series. Add a component here
 * when a chart starts using one, or it silently draws without it.
 */
import { init, use } from 'echarts/core'
import { CustomChart, LineChart } from 'echarts/charts'
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TooltipComponent,
  VisualMapComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([
  LineChart,
  CustomChart,
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  VisualMapComponent,
  LegendComponent,
  MarkLineComponent,
  CanvasRenderer,
])

export { init }
