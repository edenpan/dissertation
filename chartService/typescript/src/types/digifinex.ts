/**
 * 请求参数
 */
export interface ReqParam {
    /*
    交易币
    */
    currency_mark: string,
    /*
    交易币 id
    */
    currency: string,
    /*
    基础币 id
    */
    basemark: string;
    /** k线时间
     * time 请求的时间数据
	（
		kline_1m : 1分钟
		kline_5m ：5分钟
		kline_15m：15分钟
		kline_30m：30分钟
		kline_1h : 1小时
		kline_1d : 1天
		kline_1w : 1周
	）
     */
    time: string,
    /*
    时间戳
    */
    ts: number,
    /*
    data 为要加密的数据
    */
    // data: string,
    /**
     * 请求签名
     * 对对象进行排序拼接
     sign 为排序对象  key 为加密暗号
     */
    // sign: string;
}

/**
 * 请求参数
 */
export interface ReqParams {
    /*
    交易币
    */
    currency_mark?: string,

}
