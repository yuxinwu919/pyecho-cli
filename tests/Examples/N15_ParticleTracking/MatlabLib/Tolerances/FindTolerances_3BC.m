function [Z1,Z2,Z3,dZdX1,dZdY1,dZdX2,dZdY2,dZdX3,dZdY3]...
    =FindTolerances_3BC(E0,zeta1,k,V1,f1,V13,f13,V2,f2,V3,f3,...
    r56,r562,r563,t56,t562,t563)

X1=V1*cos(f1)+V13*cos(f13);Y1=V1*sin(f1)+3*V13*sin(f13);
X2=V2*cos(f2);Y2=V2*sin(f2);
X3=V3*cos(f3);Y3=V3*sin(f3);

E1=E0+X1;E2=E1 +X2; E3=E2+X3;

e1s=(E0*zeta1 - k*Y1)/E1;
Z1=1 - r56*e1s;
e2s=(e1s*E1 - k*Z1*Y2)/E2;
Z2=Z1 - r562*e2s;
e3s=(e2s*E2 - k*Z2*Y3)/E3;
Z3=Z2 - r563*e3s;

dZdX1(1) = -2*t56*e1s/E1;
e2w = 1/E2*(1 + k*Y2*r56/E1);
e2ws = 1/E2*(k^2*X2*Z1*r56/E1 - k*Y2*dZdX1(1));
dZdX1(2) = dZdX1(1) - r562*e2ws - 2*t562*e2w *e2s;

s2w = -(r56/E1) - r562*e2w;
e3w = 1/E3*(E2*e2w - k*Y3*s2w);
e3ws = 1/E3*(E2*e2ws - k^2*X3*Z2*s2w - k*Y3*dZdX1(2));
dZdX1(3) = dZdX1(2) - r563*e3ws - 2*t563*e3w*e3s;


%B=k*(r56*X2*Z1^2*(E3*r562*Z3+E2*r563*Z1)+r563*X3*Z2^2*(E2*r56*Z2+E1*r562));
%B=k*B/(E1*E2*E3*Z1*Z2);

dZdY1(1) = k*r56/E1;
e2ws = 1/E2*(-k-k*Y2*dZdY1(1));
dZdY1(2) = dZdY1(1) - r562*e2ws;
e3ws = 1/E3*(E2*e2ws - k*Y3*dZdY1(2));
dZdY1(3) = dZdY1(2) - r563*e3ws;

dZdX2(1)=0;
dZdX2(2) = -2*t562*e2s/E2;
e3w = 1/E3*(1+k*Y3*r562/E2);
e3ws = 1/E3*(k^2*X3*Z2*r562/E2-k*Y3*dZdX2(2));
dZdX2(3) = dZdX2(2) - r563*e3ws - 2*t563*e3w *e3s;

dZdY2(1)=0;
dZdY2(2) = Z1*k*r562/E2;
e3ws = 1/E3*(-k*Z1- k*Y3*dZdY2(2));
dZdY2(3) = dZdY2(2) - r563*e3ws;

dZdX3(1)=0;dZdX3(2)=0;
dZdX3(3) = -2*t563*e3s/E3;
dZdY3(1)=0;dZdY3(2)=0;
dZdY3(3) = Z2*k*r563/E3;

