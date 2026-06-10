# 概念漂移检测报告
生成时间: 2026-06-10 18:13:42

## 评估标准
- PSI < 0.1: 稳定
- PSI 0.1 - 0.25: 中度漂移
- PSI > 0.25: 显著漂移（需关注）

## 显著漂移特征 (PSI > 0.25)
- loan_amnt @ 2008: PSI=0.2972
- int_rate @ 2008: PSI=0.5318
- fico_avg @ 2008: PSI=0.7293
- annual_inc @ 2008: PSI=0.3307
- dti @ 2008: PSI=0.2738
- loan_amnt @ 2009: PSI=0.4133
- int_rate @ 2009: PSI=2.1773
- fico_avg @ 2009: PSI=2.9081
- annual_inc @ 2009: PSI=0.3736
- dti @ 2009: PSI=0.3795
- installment @ 2009: PSI=0.3423
- int_rate @ 2010: PSI=0.2795
- fico_avg @ 2010: PSI=2.8696
- annual_inc @ 2010: PSI=0.2929
- dti @ 2010: PSI=0.3862
- loan_amnt @ 2011: PSI=0.3147
- int_rate @ 2011: PSI=0.2881
- fico_avg @ 2011: PSI=2.8981
- annual_inc @ 2011: PSI=0.3822
- dti @ 2011: PSI=0.4629
- installment @ 2011: PSI=0.3294
- loan_amnt @ 2012: PSI=0.5439
- int_rate @ 2012: PSI=0.6134
- fico_avg @ 2012: PSI=2.9040
- annual_inc @ 2012: PSI=0.4729
- dti @ 2012: PSI=0.7800
- revol_util @ 2012: PSI=0.5051
- installment @ 2012: PSI=0.5771
- loan_amnt @ 2013: PSI=0.7681
- int_rate @ 2013: PSI=0.5320
- fico_avg @ 2013: PSI=3.0478
- annual_inc @ 2013: PSI=0.5704
- dti @ 2013: PSI=0.9228
- revol_util @ 2013: PSI=0.6986
- installment @ 2013: PSI=0.8699
- open_acc @ 2013: PSI=0.2548
- loan_amnt @ 2014: PSI=0.6986
- int_rate @ 2014: PSI=0.5598
- fico_avg @ 2014: PSI=3.0365
- annual_inc @ 2014: PSI=0.5125
- dti @ 2014: PSI=0.9696
- revol_util @ 2014: PSI=0.6532
- installment @ 2014: PSI=0.7899
- loan_amnt @ 2015: PSI=0.6874
- int_rate @ 2015: PSI=0.5908
- fico_avg @ 2015: PSI=3.0092
- annual_inc @ 2015: PSI=0.4800
- dti @ 2015: PSI=0.9453
- revol_util @ 2015: PSI=0.5443
- installment @ 2015: PSI=0.7274
- loan_amnt @ 2016: PSI=0.5788
- int_rate @ 2016: PSI=0.4781
- fico_avg @ 2016: PSI=2.9675
- annual_inc @ 2016: PSI=0.5056
- dti @ 2016: PSI=0.8756
- revol_util @ 2016: PSI=0.4374
- installment @ 2016: PSI=0.6115
- loan_amnt @ 2017: PSI=0.4804
- int_rate @ 2017: PSI=0.4204
- fico_avg @ 2017: PSI=2.8920
- annual_inc @ 2017: PSI=0.4553
- dti @ 2017: PSI=0.7886
- revol_util @ 2017: PSI=0.3612
- installment @ 2017: PSI=0.4917
- loan_amnt @ 2018: PSI=0.4438
- int_rate @ 2018: PSI=0.2761
- fico_avg @ 2018: PSI=2.8151
- annual_inc @ 2018: PSI=0.4132
- dti @ 2018: PSI=0.4943
- revol_util @ 2018: PSI=0.2658
- installment @ 2018: PSI=0.4484

## 中度漂移特征 (PSI 0.1 - 0.25)
- revol_util @ 2008: PSI=0.1046
- installment @ 2008: PSI=0.2079
- revol_util @ 2009: PSI=0.1672
- open_acc @ 2009: PSI=0.1359
- loan_amnt @ 2010: PSI=0.2477
- revol_util @ 2010: PSI=0.1204
- installment @ 2010: PSI=0.1994
- open_acc @ 2010: PSI=0.1041
- revol_util @ 2011: PSI=0.1902
- open_acc @ 2011: PSI=0.1127
- open_acc @ 2012: PSI=0.1914
- open_acc @ 2014: PSI=0.2443
- open_acc @ 2015: PSI=0.2253
- open_acc @ 2016: PSI=0.2153
- open_acc @ 2017: PSI=0.1661
- open_acc @ 2018: PSI=0.1187

## 建模建议
1. 对于 PSI > 0.25 的特征，考虑按年份分段建模或在特征中加入年份交互项。
2. 若违约率趋势存在结构性断点（如 2008 金融危机），应评估是否需要剔除或标记该时段。