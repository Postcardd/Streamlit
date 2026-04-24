import subprocess

result = subprocess.run(['sh', 'vwpt="38646" uuid="5c69b8a1-a5d2-4dff-8654-a03eaa68d558" argo="vwpt" agn="idx.anni.cc.cd" agk="eyJhIjoiODYwMzYyNmRiMmE3MTgxMDBiMmRkNzcwNTg4MWVmMDAiLCJ0IjoiYjhmOTU4ZmMtMjAxMy00Y2EwLTk0NTUtN2ViZmE2OGY0YjRiIiwicyI6IllXVTJZakU1Tm1FdE9HTmlOeTAwTUdZM0xXRTVNell0TWpkaFptVmtOR1F4WmprMyJ9" bash <(curl -Ls https://raw.githubusercontent.com/yonggekkk/argosbx/main/argosbx.sh)
'], capture_output=True, text=True)
print(result.stdout)
