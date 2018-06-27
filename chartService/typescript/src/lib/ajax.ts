import { Component, HttpStatus } from '@nestjs/common';
import { ReqParam, ReqParams} from '../types';
// import * as jquery from '@types/jquery';
import * as nanoajax from 'nanoajax';
import { Util } from 'ns-common';
import * as querystring from 'querystring';
import * as md5 from 'md5';
import * as authcode from 'authcode';

export class ObejSort {
    static async strsort(sign, key) {
        let NewSign = '';
        const sdic = Object.keys(sign).sort();
        for (let ki = 0; ki < sdic.length; ki++) {
            NewSign += (sdic[ki] + '=' + sign[sdic[ki]] + '&');
        }

        return md5(NewSign + key);
    }
}


export class Finance {
    static async getHistory(reqParam: ReqParam) {
        const baseUrl = 'https://www.digifinex.com/orders/getOrdersKline?'

        const signArr = {
            currency_mark: reqParam.currency_mark,
            currency: reqParam.currency,
            basemark: reqParam.basemark,
            time: reqParam.time
        }
        const signstr = await ObejSort.strsort(signArr, '@#shuzibi#@');

        const dataArr = {
            currency_mark: reqParam.currency_mark,
            currency: reqParam.currency,
            basemark: reqParam.basemark,
            time: reqParam.time,
            ts: reqParam.ts
        }
        const data = authcode(encodeURI(JSON.stringify(dataArr)), 'ENCODE', 'szbrmb', '');
        const opt = {
            currency_mark: reqParam.currency_mark,
            currency: reqParam.currency,
            basemark: reqParam.basemark,
            time: reqParam.time,
            ts: reqParam.ts,
            data: data,
            sign: signstr
            };

        const url = baseUrl + querystring.stringify(opt);
        const res = await Util.fetch(url);
        const jsonlist: { [index: string]: any } = await res.json();

        // return authcode(encodeURI(JSON.stringify(dataArr)), 'ENCODE', 'szbrmb', '');
        return jsonlist
    }
    static async currencyList() {
        const baseUrl = 'https://www.digifinex.com/cron/currency_list_handle'
        const res = await Util.fetch(baseUrl);
        const jsonRes: { [index: string]: any } = await res.json()

        return jsonRes;
    }

    static async currencyData() {
        const baseUrl = 'https://www.digifinex.com/cron/currency_list_handle'
        const res = await Util.fetch(baseUrl);
        const jsonRes = await res.json()

        return jsonRes;
    }
}


