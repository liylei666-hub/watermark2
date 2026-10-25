# Windows网络恢复后的一次新请求：相同证书错误

用户说明网络可能已恢复并明确要求再试后，已先核实断连前报告写入完成、没有遗留curl下载进程和部分ZIP，随后对同一官方HTTPS地址进行一次新请求。

2026-10-25 05:06:18 UTC结束：curl60、`SEC_E_WRONG_PRINCIPAL (0x80090322)`，约0.687331秒，HTTP000、正文0字节。保持正常证书验证、连接20秒/总600秒超时、256MiB文件上限、自动重试0；未修改代理、DNS、信任设置或降级HTTP。出现相同安全错误后停止，未再次请求。

[原始错误](metadata.stderr.log)、[传输字段](metadata.curl.txt)、[执行时间](terminal.json)、[事后核验](verification.json)及[四次执行公开复核](public_verification.json)保留。[首次Windows尝试](../confirmation100_assets_windows_v1/report.md)的执行文件和封存清单均未改变；它与[服务器两次超时](../confirmation100_assets_v1_retry1/report.md)分开记载。

没有ZIP，因此没有可宣称完成的ZIP完整性/整包哈希或双端SCP哈希检查。100张载体/100条caption仍未取得，无SCP、GPU、模型或攻击优化。原冻结选择规则及历史覆盖清单不变。用户随后允许核实可信镜像，替代来源审查正在父线程进行；本记录不把未知镜像当作可信来源，不猜测地址发起下载。任何后续取得链路须新增来源与版本验证记录。
