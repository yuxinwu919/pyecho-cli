function cT=TimeDelay(P0,P1,L)
PhysConsts;
E0=P0(:,2)*1e6;
E1=P1(:,2)*1e6;
g0=E0/E00;
g1=E1/E00;
ind=find(g0==g1);
cT(ind,1)=g0(ind)./sqrt(g0(ind).*g0(ind)-1)*L;
ind=find(g0~=g1);
cT(ind,1)=(sqrt(g0(ind).*g0(ind)-1)-sqrt(g1(ind).*g1(ind)-1))./(g0(ind)-g1(ind))*L;
cT=cT-cT(1);
