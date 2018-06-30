import { Component, HttpStatus } from '@nestjs/common';
import { ReqParam} from '../types';

import * as IDatafeed from './datafeed-api.d';
import * as fetch from 'isomorphic-fetch';
import { Hesonogoma, GoogleFinance, GApiOutPut } from 'ns-findata';
import * as getData from './ajax';
import * as nanoajax from 'nanoajax';
import { Util } from 'ns-common';
import * as md5 from 'md5';

export interface UdfCompatibleConfiguration extends IDatafeed.DatafeedConfiguration {
  supports_search?: boolean;
  supports_group_request?: boolean;
}


const hg: Hesonogoma = new Hesonogoma();
const supported_resolutions = ['1', '5', '15', '30', '60', '4h', '1D'];
// tslint:disable-next-line:max-line-length
const HSIList = [['0939', 'China Construction Bank', 'China Construction Bank', '0939'],
['0005', 'HSBC Holdings plc', 'HSBC Holdings plc', '0005'],
['1299', 'AIA Group Limited', 'AIA Group Limited', '1299'],
['1398', 'Industrial and Commercial Bank of China', 'Industrial and Commercial Bank of China', '1398'],
['2388', 'BOC Hong Kong (Holdings) Ltd', 'BOC Hong Kong (Holdings) Ltd', '2388'],
['2318', 'Ping An Insurance', 'Ping An Insurance', '2318'],
['3988', 'Bank of China Ltd', 'Bank of China Ltd', '3988'],
['3328', 'Bank of Communications Ltd', 'Bank of Communications Ltd', '3328'],
['0011', 'Hang Seng Bank Ltd', 'Hang Seng Bank Ltd', '0011'],
['2628', 'China Life', 'China Life', '2628'],
['0388', 'HKEx Limited', 'HKEx Limited', '0388'],
['0023', 'Bank of East Asia, Ltd', 'Bank of East Asia, Ltd', '0023'],
['0002', 'CLP Holdings Limited', 'CLP Holdings Limited', '0002'],
['0003', 'Hong Kong and China Gas Company Limited', 'Hong Kong and China Gas Company Limited', '0003'],
['0006', 'Power Assets Holdings Limited', 'Power Assets Holdings Limited', '0006'],
['0836', 'China Resources Power', 'China Resources Power', '0836'],
['1038', 'Cheung Kong Infrastructure Holdings Limited', 'Cheung Kong Infrastructure Holdings Limited', '1038'],
['0016', 'Sun Hung Kai Properties Limited', 'Sun Hung Kai Properties Limited', '0016'],
['1113', 'CK Property Holdings Limited', 'CK Property Holdings Limited', '1113'],
['0688', 'China Overseas Land & Investment Limited', 'China Overseas Land & Investment Limited', '0688'],
['0004', 'Wharf (Holdings) Limited', 'Wharf (Holdings) Limited', '0004'],
['0012', 'Henderson Land Development Company Limited', 'Henderson Land Development Company Limited', '0012'],
['1109', 'China Resources Land Limited', 'China Resources Land Limited', '1109'],
['0101', 'Hang Lung Properties Limited', 'Hang Lung Properties Limited', '0101'],
['0017', 'New World Development Company Limited', 'New World Development Company Limited', '0017'],
['0083', 'Sino Land Company Limited', 'Sino Land Company Limited', '0083'],
['0823', 'The Link REIT', 'The Link REIT', '0823'],
['0941', 'China Mobile Ltd', 'China Mobile Ltd', '0941'],
['0700', 'Tencent Holdings Limited', 'Tencent Holdings Limited', '0700'],
['0883', 'CNOOC Ltd', 'CNOOC Ltd', '0883'],
['0001', 'CK Hutchison Holdings Limited', 'CK Hutchison Holdings Limited', '0001'],
['0267', 'CITIC Pacific Ltd', 'CITIC Pacific Ltd', '0267'],
['1928', 'Sands China', 'Sands China', '1928'],
['0762', 'China Unicom (Hong Kong) Limited', 'China Unicom (Hong Kong) Limited', '0762'],
['0027', 'Galaxy Entertainment Group Ltd.', 'Galaxy Entertainment Group Ltd.', '0027'],
['0066', 'MTR Corporation Ltd', 'MTR Corporation Ltd', '0066'],
['0857', 'PetroChina Company Limited', 'PetroChina Company Limited', '0857'],
['0386', 'Sinopec Corp', 'Sinopec Corp', '0386'],
['0151', 'Want Want China Holdings Ltd', 'Want Want China Holdings Ltd', '0151'],
['0992', 'Lenovo Group', 'Lenovo Group', '0992'],
['0322', 'Tingyi (Cayman Islands) Holding Corp', 'Tingyi (Cayman Islands) Holding Corp', '0322'],
['1044', 'Hengan International Group Co. Ltd', 'Hengan International Group Co. Ltd', '1044'],
['0019', 'Swire Group', 'Swire Group', '0019'],
['1088', 'China Shenhua Energy', 'China Shenhua Energy', '1088'],
['1880', 'Belle International', 'Belle International', '1880'],
['0144', 'China Merchants Holdings (International)', 'China Merchants Holdings (International)', '0144'],
['0293', 'Cathay Pacific Airways Ltd', 'Cathay Pacific Airways Ltd', '0293'],
['2319', 'Mengniu Dairy', 'Mengniu Dairy', '2319'],
['0135', 'Kunlun Energy', 'Kunlun Energy', '0135'],
['0175', 'Geely Auto', 'Geely Auto', '0175']]

@Component()
export class DatafeedService {
  constructor() { }

  getConfig(): UdfCompatibleConfiguration {
    return {
      supports_search: true,
      supports_group_request: false,
      supported_resolutions,
      supports_marks: false,
      supports_time: true
    };
  }

  getServerTime() {
    return Math.floor(Date.now()) + '';
  }

  async resolveSymbol(symbolName: string) {
    const res = HSIList;
    if (!res || res.length === 0) {
      return;
    }
    const symbolInfo = res.find(o => {

      return o[0] === symbolName;
    });
    if (!symbolInfo) {
      return;
    }
    return {
      name: symbolInfo[0],
      full_name: symbolInfo[1],
      ticker: symbolInfo[0],
      description: symbolInfo[0] + '-' + symbolInfo[1],
      type: 'stock',
      session: '0930-1200,1300-1600',
      exchange: '香港证券交易所',
      listed_exchange: '香港证券交易所',
      timezone: 'Asia/Hong_Kong',
      pricescale: 100,
      minmov: 1,
      has_intraday: true,
      supported_resolutions,
      has_daily: true,
      has_weekly_and_monthly: true,
      has_no_volume: false,
      sector: symbolInfo[2],
      industry: symbolInfo[3],
      currency_code: 'HKD',
    }
  }

  async getHistory(symbolName: string, from: number, to: number, resolution: string) {
    let time = 'day'
    switch (resolution) {
      case '1':
        time = '1minutes'
        break;
      case '5':
        time = '5minutes'
        break;
      case '15':
        time = '15minutes'
        break;
      case '30':
        time = '30minutes'
        break;
      case '60':
        time = 'hour'
        break;
      case '4h':
        time = '4hours'
        break;
      case '1D':
        time = 'day'
        break;
    }
    const opt = {
      q: symbolName,
      starttime: from,
      endtime: to,
      resolution: time
    };
    const hisRes = await GoogleFinance.getHistory(opt);
    const t: number[] = [], c: number[] = [], o: number[] = [], l: number[] = [], h: number[] = [], v: number[] = [];
    hisRes.forEach((obj: GApiOutPut) => {
      t.push(obj.time);
      if (obj.close) {
        c.push(obj.close);
      }
      if (obj.open) {
        o.push(obj.open);
      }
      if (obj.low) {
        l.push(obj.low);
      }
      if (obj.high) {
        h.push(obj.high);
      }
      if (obj.volume) {
        v.push(obj.volume);
      }
    })
    return {s: 'ok', t, c, o, l, h, v}
  }

  async searchSymbols(
    userInput: string,
    exchange: string,
    symbolType: string,
    maxRecords?: number,
  ): Promise<IDatafeed.SearchSymbolResultItem[] | undefined> {
    // const res = <string[][]> await hg.getFindDataInfo(hg.Data.Nikkei225);
    const res = HSIList;
    if (!res || res.length === 0) {
      return;
    }
    const searchItem: IDatafeed.SearchSymbolResultItem[] = [];
    res.forEach(o => {
      if (o && o.length !== 0) {
        const item: IDatafeed.SearchSymbolResultItem = {
          symbol: o[0],
          full_name: o[1],
          description: o[1] + '-' + o[2],
          exchange: '',
          ticker: o[0],
          type: 'stock'
        };
        searchItem.push(item);
      }
    });
    return searchItem;
  }
  //   const reslist = await getData.Finance.currencyList();
  //   const res = reslist.currency_list.USDT
  //   if (!res || res.length === 0) {
  //     return;
  //   }
  //   const searchItems: IDatafeed.SearchSymbolResultItem[] = [];
  //   res.forEach(o => {
  //     if (o && o.length !== 0) {
  //       const item: IDatafeed.SearchSymbolResultItem = {
  //         symbol: o.currency_mark,
  //         full_name: o.currency_name,
  //         description:  o.currency_intro,
  //         exchange: 'digifinex',
  //         ticker: o.currency_mark,
  //         type: '交易所'
  //       };
  //       searchItems.push(item);
  //     }
  //   });
  //   return searchItems;
  // }

}
