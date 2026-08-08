function GR=FindGRA(C,L_p)
%roots of polynomial L()L+iC)^2=i
i=complex(0,1);
p=[1 2*i*C -C*C+L_p*L_p -i];
r=roots(p);
GR=max(real(r));