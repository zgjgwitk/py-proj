# ---- 功能说明 ----
1. 读取同目录下的 [msg_callback_log.xlsx] 文件, 第一列 [LogInfo] 就是需要解析的日志内容
2. 解析日志内容有以下几个处理分支:
  2.1 "创蓝国内短信结果回调-ClSmsResult:"开头的日志, 使用 AnalyseClSmsResult() 方法解析
   - 请求的接口定义为[HttpGet][Route("/api/callback/ClSmsResult")] ClSmsResult(string receiver, string pswd, string msgid, string reportTime, string mobile, string status,
            string notifyTime, string statusDesc, string uid, int length, int brandId = 0)
   - 解析日志中的json参数, 组装请求此接口
  2.2 "创蓝国际短信结果回调-ClSmsResult:"开头的日志, 使用 AnalyseInterClSmsResult() 方法解析
   - 请求的接口定义为[HttpGet][Route("/api/callback/ClInterSmsResult")] ClInterSmsResult(string receiver, string pswd, string msgid, string reportTime, string notifyTime,
            string mobile, string status, string batchSeq, int brandId = 0)
   - 请求日志uid, 调用接口时换成 batchSeq
   - 解析日志中的json参数, 组装请求此接口
  2.3 "创蓝视频短信回调接口-ClVideoResult:"开头的日志, 使用 AnalyseClVideoResult() 方法解析
   - 请求的接口定义为[HttpPost][Route("/api/callback/ClVideoResult")] ClVideoResult([FromBody] List<ClVideoCallbackInfo> reqData, int brandId = 0)
   - 解析日志中的json, 作为请求body, 组装请求此接口
  2.4 "创蓝国内短信回送上行明细回调-ClSmsReply:"开头的日志, 使用 AnalyseClSmsReply() 方法解析
   - 请求的接口定义为[HttpGet][Route("/api/callback/ClSmsReply")] ClSmsReply(string receiver, string pswd, string moTime, string mobile, string msg,
             string destcode, string spCode, string notifyTime, string extend)
3. 将响应内容回填到 [msg_callback_log.xlsx] 文件的 [Response] 列